"""Generic comment sync — Release 0.8.0 (ADR-020). Mirrors
youtube_comment_sync.py exactly, but drives any PlatformAdapter and writes to
the generic ContentCommentThread/ContentComment tables instead of the
YouTube-specific ones. Upsert-only — a thread/comment is never deleted just
because a later sync omits it."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import MetricSnapshot, Publication
from app.models.content_comments import ContentComment, ContentCommentThread
from app.models.integration import PlatformAccount, SyncRun
from app.services.platforms.base import PlatformAdapter, RawComment, RawCommentThread

STALE_RUN_MINUTES = 30


class ContentCommentSyncAlreadyRunningError(Exception):
    pass


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _sync_platform_name(platform: str) -> str:
    return f"{platform}_comments"


def _reclaim_stale_running_run(db: Session, platform: str) -> None:
    sync_platform = _sync_platform_name(platform)
    running = db.scalar(select(SyncRun).where(SyncRun.platform == sync_platform, SyncRun.status == "running"))
    if running is None:
        return
    if datetime.now(timezone.utc) - _aware(running.started_at) <= timedelta(minutes=STALE_RUN_MINUTES):
        raise ContentCommentSyncAlreadyRunningError(f"Synchronizacja komentarzy ({platform}) już trwa.")
    running.status = "failed"
    running.error_message = "Przerwana — proces został prawdopodobnie zrestartowany w trakcie synchronizacji."
    running.finished_at = datetime.now(timezone.utc)
    db.commit()


def _upsert_thread(db: Session, platform: str, publication: Publication, thread: RawCommentThread) -> tuple[ContentCommentThread, bool]:
    existing = db.scalar(select(ContentCommentThread).where(ContentCommentThread.platform_thread_id == thread.external_id))
    is_new = existing is None
    row = existing or ContentCommentThread(platform_thread_id=thread.external_id, top_level_comment_id=thread.top_level.external_id)

    now = datetime.now(timezone.utc)
    row.platform = platform
    row.publication_id = publication.id
    row.top_level_comment_id = thread.top_level.external_id
    row.author_external_id = thread.top_level.author_external_id
    row.author_display_name = thread.top_level.author_display_name
    row.author_avatar_url = thread.top_level.author_avatar_url
    row.text_original = thread.top_level.text
    row.like_count = thread.top_level.like_count
    row.published_at = thread.top_level.published_at
    row.updated_at = thread.top_level.published_at
    row.total_reply_count = thread.total_reply_count
    row.can_reply = thread.can_reply
    row.last_synced_at = now
    if is_new:
        row.imported_at = now
        db.add(row)
        db.flush()
    return row, is_new


def _upsert_reply(db: Session, platform: str, thread: ContentCommentThread, reply: RawComment) -> bool:
    existing = db.scalar(select(ContentComment).where(ContentComment.platform_comment_id == reply.external_id))
    is_new = existing is None
    row = existing or ContentComment(
        platform_comment_id=reply.external_id,
        thread_id=thread.id,
        parent_comment_id=reply.parent_external_id or thread.top_level_comment_id,
    )
    now = datetime.now(timezone.utc)
    row.platform = platform
    row.thread_id = thread.id
    row.parent_comment_id = reply.parent_external_id or thread.top_level_comment_id
    row.author_external_id = reply.author_external_id
    row.author_display_name = reply.author_display_name
    row.author_avatar_url = reply.author_avatar_url
    row.text_original = reply.text
    row.like_count = reply.like_count
    row.published_at = reply.published_at
    row.updated_at = reply.published_at
    row.is_own_reply = reply.is_own
    row.last_synced_at = now
    if is_new:
        row.imported_at = now
        db.add(row)
    return is_new


def sync_platform_comments(db: Session, account: PlatformAccount, adapter: PlatformAdapter, publication_id: Optional[int] = None) -> SyncRun:
    _reclaim_stale_running_run(db, account.platform)

    run = SyncRun(platform=_sync_platform_name(account.platform), status="running")
    db.add(run)
    db.commit()

    try:
        statement = select(Publication).where(
            Publication.platform == account.platform,
            Publication.platform_account_id == account.id,
        )
        if publication_id is not None:
            statement = statement.where(Publication.id == publication_id)
        publications = db.scalars(statement).all()
        run.videos_discovered = len(publications)
        db.commit()

        threads_discovered = 0
        comments_imported = 0
        replies_imported = 0
        items_failed = 0

        publications_processed = 0
        for publication in publications:
            try:
                with db.begin_nested():
                    latest_snapshot = db.scalar(
                        select(MetricSnapshot)
                        .where(MetricSnapshot.publication_id == publication.id)
                        .order_by(MetricSnapshot.captured_at.desc())
                        .limit(1)
                    )
                    # Meta already supplies comments_count with each media/post.
                    # Avoid one remote Graph call per historical item when the
                    # platform explicitly reports zero comments. Publications
                    # without a snapshot are still checked conservatively.
                    if latest_snapshot is not None and latest_snapshot.comments == 0:
                        continue
                    raw_threads = adapter.list_comment_threads(publication.external_id)
                    for raw_thread in raw_threads:
                        threads_discovered += 1
                        thread_row, is_new_thread = _upsert_thread(db, account.platform, publication, raw_thread)
                        if is_new_thread:
                            comments_imported += 1
                        for reply in raw_thread.replies:
                            if _upsert_reply(db, account.platform, thread_row, reply):
                                replies_imported += 1
            except Exception:
                items_failed += 1
            finally:
                publications_processed += 1
                if publications_processed % 5 == 0 or publications_processed == len(publications):
                    run.videos_updated = publications_processed
                    run.videos_failed = items_failed
                    run.threads_discovered = threads_discovered
                    run.comments_imported = comments_imported
                    run.replies_imported = replies_imported
                    db.commit()

        run.status = "success" if items_failed == 0 else "partial"
        run.videos_discovered = len(publications)
        run.videos_updated = publications_processed
        run.videos_failed = items_failed
        run.threads_discovered = threads_discovered
        run.comments_imported = comments_imported
        run.replies_imported = replies_imported
        if items_failed:
            run.error_message = f"{items_failed} z {len(publications)} pozycji nie udało się zsynchronizować (komentarze)."
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        return run
    except Exception as exc:
        db.rollback()
        failed = db.get(SyncRun, run.id)
        if failed:
            failed.status = "failed"
            failed.error_message = str(exc)[:2000]
            failed.finished_at = datetime.now(timezone.utc)
            db.commit()
        raise
