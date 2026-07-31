"""Generic platform content sync — Release 0.8.0 (ADR-020).

Drives ANY PlatformAdapter (Facebook, Instagram, future TikTok) into the unified
`ContentVideo`/`Publication`/`MetricSnapshot` engine. Mirrors
`youtube_sync.py`'s idempotency pattern exactly (overlap guard, stale-run
reclaim, per-item fault isolation via SQL savepoint, time-window snapshot
dedup) — one generic implementation instead of a copy per platform.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.content import ContentVideo, MetricSnapshot, Publication
from app.models.content_comments import ContentCommentThread
from app.models.integration import PlatformAccount, SyncRun
from app.services.platforms.base import PlatformAdapter

STALE_RUN_MINUTES = 30
MIN_SNAPSHOT_INTERVAL_MINUTES = 5


class ContentSyncAlreadyRunningError(Exception):
    pass


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _reclaim_stale_running_run(db: Session, platform: str) -> None:
    running = db.scalar(select(SyncRun).where(SyncRun.platform == platform, SyncRun.status == "running"))
    if running is None:
        return
    if datetime.now(timezone.utc) - _aware(running.started_at) <= timedelta(minutes=STALE_RUN_MINUTES):
        raise ContentSyncAlreadyRunningError(f"Synchronizacja ({platform}) już trwa — poczekaj na jej zakończenie.")
    running.status = "failed"
    running.error_message = "Przerwana — proces został prawdopodobnie zrestartowany w trakcie synchronizacji."
    running.finished_at = datetime.now(timezone.utc)
    db.commit()


def _upsert_publication(db: Session, account: PlatformAccount, item) -> Publication:
    publication = db.scalar(
        select(Publication).where(Publication.platform == account.platform, Publication.external_id == item.external_id)
    )
    if publication is None:
        content_video = ContentVideo(
            title=item.title,
            description=item.description,
            duration_seconds=item.duration_seconds,
            thumbnail_url=item.thumbnail_url,
        )
        db.add(content_video)
        db.flush()
        publication = Publication(
            content_video_id=content_video.id,
            platform_account_id=account.id,
            platform=account.platform,
            external_id=item.external_id,
            url=item.url,
            published_at=item.published_at,
        )
        db.add(publication)
        db.flush()
    else:
        # Reconnecting a Meta account deletes and recreates PlatformAccount.
        # Publication keeps its historical data because the FK uses SET NULL,
        # so every successful upsert must attach it to the current account
        # again. Without this, comments are imported but the inbox (correctly)
        # filters them out as belonging to no connected account.
        publication.platform_account_id = account.id
        publication.content_video.title = item.title
        publication.content_video.description = item.description
        publication.content_video.duration_seconds = item.duration_seconds
        publication.content_video.thumbnail_url = item.thumbnail_url
        publication.url = item.url
    return publication


def _merge_item_into_snapshot(snapshot: MetricSnapshot, item) -> None:
    for name in ("views", "likes", "comments", "shares", "saves"):
        setattr(snapshot, name, max(getattr(snapshot, name), getattr(item, name)))
    for name in ("reach", "impressions", "watch_time_seconds", "followers_gained"):
        setattr(snapshot, name, _max_optional(getattr(snapshot, name), getattr(item, name)))


def _upsert_snapshot(db: Session, publication: Publication, item, now: datetime, merge_recent: bool = False) -> bool:
    last = db.scalar(
        select(MetricSnapshot).where(MetricSnapshot.publication_id == publication.id).order_by(MetricSnapshot.captured_at.desc()).limit(1)
    )
    if last is not None and now - _aware(last.captured_at) < timedelta(minutes=MIN_SNAPSHOT_INTERVAL_MINUTES):
        if merge_recent:
            _merge_item_into_snapshot(last, item)
        return False
    db.add(
        MetricSnapshot(
            publication_id=publication.id,
            captured_at=now,
            views=item.views,
            likes=item.likes,
            comments=item.comments,
            shares=item.shares,
            saves=item.saves,
            reach=item.reach,
            impressions=item.impressions,
            watch_time_seconds=item.watch_time_seconds,
            followers_gained=item.followers_gained,
        )
    )
    return True


def _max_optional(left: Optional[int], right: Optional[int]) -> Optional[int]:
    values = [value for value in (left, right) if value is not None]
    return max(values) if values else None


def _merge_snapshot(target: MetricSnapshot, duplicate: MetricSnapshot) -> None:
    """Keep the best observation when both Graph edges were captured together."""
    for name in ("views", "likes", "comments", "shares", "saves"):
        setattr(target, name, max(getattr(target, name), getattr(duplicate, name)))
    for name in ("reach", "impressions", "watch_time_seconds", "followers_gained"):
        setattr(target, name, _max_optional(getattr(target, name), getattr(duplicate, name)))


def _merge_alternate_publication(db: Session, canonical: Publication, alternate_external_id: str) -> bool:
    """Merge one legacy wrapper publication into its canonical video.

    Snapshots captured at the same instant are combined field-by-field; other
    history points and any comment threads are moved to the canonical row.
    The now-orphaned ContentVideo is removed only after its last Publication is
    gone. Returns True when a legacy duplicate was found and merged.
    """
    duplicate = db.scalar(
        select(Publication).where(
            Publication.platform == canonical.platform,
            Publication.external_id == alternate_external_id,
        )
    )
    if duplicate is None or duplicate.id == canonical.id:
        return False

    duplicate_video_id = duplicate.content_video_id
    canonical_snapshots = {
        snapshot.captured_at: snapshot
        for snapshot in db.scalars(select(MetricSnapshot).where(MetricSnapshot.publication_id == canonical.id)).all()
    }
    duplicate_snapshots = db.scalars(
        select(MetricSnapshot).where(MetricSnapshot.publication_id == duplicate.id).order_by(MetricSnapshot.captured_at)
    ).all()
    for snapshot in duplicate_snapshots:
        existing = canonical_snapshots.get(snapshot.captured_at)
        if existing is not None:
            _merge_snapshot(existing, snapshot)
            db.delete(snapshot)
        else:
            snapshot.publication = canonical
            canonical_snapshots[snapshot.captured_at] = snapshot

    db.execute(
        update(ContentCommentThread)
        .where(ContentCommentThread.publication_id == duplicate.id)
        .values(publication_id=canonical.id)
    )
    db.flush()
    db.delete(duplicate)
    db.flush()

    remaining = db.scalar(select(func.count(Publication.id)).where(Publication.content_video_id == duplicate_video_id)) or 0
    if remaining == 0:
        orphan = db.get(ContentVideo, duplicate_video_id)
        if orphan is not None:
            db.delete(orphan)
    return True


def _delete_excluded_publications(db: Session, platform: str, external_ids: set[str]) -> None:
    """Remove locally imported content the adapter now classifies as unsupported.

    This only changes RCC's local database; it never deletes the original item
    on the social platform. Instagram uses it to remove legacy photos/carousels
    from the Reels-only dashboard after the next synchronization.
    """
    if not external_ids:
        return
    publications = db.scalars(
        select(Publication).where(Publication.platform == platform, Publication.external_id.in_(external_ids))
    ).all()
    for publication in publications:
        content_video_id = publication.content_video_id
        db.delete(publication)
        db.flush()
        remaining = db.scalar(select(func.count(Publication.id)).where(Publication.content_video_id == content_video_id)) or 0
        if remaining == 0:
            orphan = db.get(ContentVideo, content_video_id)
            if orphan is not None:
                db.delete(orphan)


def sync_platform_content(db: Session, account: PlatformAccount, adapter: PlatformAdapter) -> SyncRun:
    _reclaim_stale_running_run(db, account.platform)

    run = SyncRun(platform=account.platform, status="running")
    db.add(run)
    db.commit()

    try:
        items = adapter.list_content_items()
        excluded_content_ids = set(getattr(adapter, "excluded_content_ids", set()))
        _delete_excluded_publications(db, account.platform, excluded_content_ids)
        run.videos_discovered = len(items)
        db.commit()
        now = datetime.now(timezone.utc)
        imported = 0
        updated = 0
        snapshots_created = 0
        snapshots_deduplicated = 0
        items_failed = 0

        for index, item in enumerate(items, start=1):
            try:
                with db.begin_nested():
                    existing = db.scalar(
                        select(Publication).where(Publication.platform == account.platform, Publication.external_id == item.external_id)
                    )
                    is_new = existing is None
                    publication = _upsert_publication(db, account, item)
                    merged_alternate = False
                    for alternate_external_id in item.alternate_external_ids:
                        if _merge_alternate_publication(db, publication, alternate_external_id):
                            merged_alternate = True
                    if is_new:
                        imported += 1
                    else:
                        updated += 1
                    if _upsert_snapshot(db, publication, item, now, merge_recent=merged_alternate):
                        snapshots_created += 1
                    else:
                        snapshots_deduplicated += 1
            except Exception:
                items_failed += 1
            finally:
                # Persist lightweight checkpoints so the synchronization UI
                # can show real X/Y progress during a long Meta import.
                if index % 5 == 0 or index == len(items):
                    run.imported_items = imported
                    run.videos_updated = updated
                    run.snapshots_created = snapshots_created
                    run.snapshots_deduplicated = snapshots_deduplicated
                    run.videos_failed = items_failed
                    db.commit()

        run.status = "success" if items_failed == 0 else "partial"
        run.imported_items = imported
        run.videos_discovered = len(items)
        run.videos_updated = updated
        run.snapshots_created = snapshots_created
        run.snapshots_deduplicated = snapshots_deduplicated
        run.videos_failed = items_failed
        if items_failed:
            run.error_message = f"{items_failed} z {len(items)} pozycji nie udało się zsynchronizować."
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


def get_publications_with_latest_snapshot(db: Session, platform: Optional[str] = None) -> list[tuple[Publication, Optional[MetricSnapshot]]]:
    """Every Publication (optionally filtered by platform) with its most recent
    MetricSnapshot — the generic equivalent of youtube_analytics._video_rows,
    shared by the generic Dashboard/Videos/Compare pages (Part 5)."""
    statement = select(Publication)
    if platform:
        statement = statement.where(Publication.platform == platform)
    publications = db.scalars(statement.order_by(Publication.published_at.desc())).all()
    results = []
    for publication in publications:
        latest = db.scalar(
            select(MetricSnapshot).where(MetricSnapshot.publication_id == publication.id).order_by(MetricSnapshot.captured_at.desc()).limit(1)
        )
        results.append((publication, latest))
    return results
