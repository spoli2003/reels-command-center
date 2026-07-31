from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.integrations.youtube.oauth import has_comments_scope
from app.models.comments import QuickReplyTemplate
from app.models.integration import SyncRun, YoutubeVideo
from app.schemas.comments import (
    CommentInboxRead,
    CommentSyncStatus,
    CommentSyncTrigger,
    CommentThreadRead,
    QuickReplyTemplateCreate,
    QuickReplyTemplateRead,
    QuickReplyTemplateUpdate,
    ReplyCreate,
    ReplyRead,
    ReplyUpdate,
)
from app.services import youtube_scheduler
from app.services.youtube_client_factory import NotConnectedError, build_youtube_client, get_connected_account_and_channel
from app.services.youtube_comment_actions import CommentActionError, delete_reply, edit_reply, post_reply
from app.services.youtube_comment_sync import CommentSyncAlreadyRunningError, sync_youtube_comments
from app.services.youtube_comments_query import build_inbox_rows, build_inbox_summary, filter_and_sort_rows
from app.services.youtube_unified_bridge import bridge_all_youtube_comments

router = APIRouter(prefix="/api/integrations/youtube", tags=["YouTube Comments"])


def _require_connected(db: Session):
    try:
        return get_connected_account_and_channel(db)
    except NotConnectedError as exc:
        raise HTTPException(409, str(exc)) from exc


def _require_comments_scope(account) -> None:
    if not has_comments_scope(account.scopes):
        raise HTTPException(
            403,
            "To konto nie ma jeszcze uprawnienia do odczytu/publikowania komentarzy (youtube.force-ssl). "
            "Połącz konto ponownie, aby zaakceptować dodatkowe uprawnienie.",
        )


def _reply_to_read(reply) -> ReplyRead:
    return ReplyRead(
        platform_comment_id=reply.platform_comment_id,
        author_channel_id=reply.author_channel_id,
        author_display_name=reply.author_display_name,
        author_avatar_url=reply.author_avatar_url,
        text_original=reply.text_original,
        like_count=reply.like_count,
        published_at=reply.published_at,
        updated_at=reply.updated_at,
        is_own_reply=reply.is_own_reply,
        viewer_rating=getattr(reply, "viewer_rating", None),
    )


def _thread_to_read(row: dict) -> CommentThreadRead:
    thread = row["thread"]
    video = row["video"]
    return CommentThreadRead(
        platform_thread_id=thread.platform_thread_id,
        youtube_video_id=video.youtube_video_id if video else "",
        video_title=video.title if video else "Film usunięty lub niezsynchronizowany",
        video_thumbnail_url=video.thumbnail_url if video else None,
        top_level_comment_id=thread.top_level_comment_id,
        author_channel_id=thread.author_channel_id,
        author_display_name=thread.author_display_name,
        author_avatar_url=thread.author_avatar_url,
        text_original=thread.text_original,
        like_count=thread.like_count,
        published_at=thread.published_at,
        updated_at=thread.updated_at,
        total_reply_count=thread.total_reply_count,
        can_reply=thread.can_reply,
        is_own_thread=row["is_own_thread"],
        conversation_state=row["conversation_state"].value,
        last_message_at=row["last_message_at"],
        is_likely_question=row["is_likely_question"],
        is_highly_liked=row["is_highly_liked"],
        priority_score=row["priority_score"],
        viewer_rating=thread.viewer_rating,
        replies=[_reply_to_read(reply) for reply in row["replies"]],
    )


@router.get("/comments", response_model=CommentInboxRead)
def list_comments(
    quick: Optional[str] = Query(None, description="mine|new|waiting|resolved|closed|unanswered|answered|questions|recent|with_replies|highly_liked"),
    video: Optional[str] = Query(None, description="Filter by youtube_video_id"),
    author: Optional[str] = Query(None, description="Filter by author display name substring"),
    q: Optional[str] = Query(None, description="Search comment text or author"),
    sort: str = Query("newest", description="newest|oldest|most_liked|most_replies|priority|recently_active"),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
):
    account, channel = _require_connected(db)
    rows = build_inbox_rows(db, channel.id, channel.youtube_channel_id)
    summary = build_inbox_summary(rows)

    video_row_id = None
    if video:
        video_row = db.scalar(select(YoutubeVideo).where(YoutubeVideo.youtube_video_id == video, YoutubeVideo.channel_id == channel.id))
        video_row_id = video_row.id if video_row else -1  # -1 never matches -> empty result for unknown video

    filtered = filter_and_sort_rows(
        rows, quick=quick, video_id=video_row_id, author=author, search=q, date_from=date_from, date_to=date_to, sort=sort
    )
    return CommentInboxRead(summary=summary, threads=[_thread_to_read(r) for r in filtered])


@router.post("/comments/sync")
def sync_comments(payload: CommentSyncTrigger, db: Session = Depends(get_db)):
    settings = get_settings()
    account, channel = _require_connected(db)
    _require_comments_scope(account)
    client = build_youtube_client(account, settings)

    video_row_id = None
    if payload.youtube_video_id:
        video_row = db.scalar(
            select(YoutubeVideo).where(YoutubeVideo.youtube_video_id == payload.youtube_video_id, YoutubeVideo.channel_id == channel.id)
        )
        if video_row is None:
            raise HTTPException(404, "Nie znaleziono filmu")
        video_row_id = video_row.id

    try:
        run = sync_youtube_comments(db, channel, client, mode=payload.mode, video_id=video_row_id)
    except CommentSyncAlreadyRunningError as exc:
        raise HTTPException(409, str(exc)) from exc
    bridge_all_youtube_comments(db, account)
    return {
        "status": run.status,
        "threads_discovered": run.threads_discovered,
        "comments_imported": run.comments_imported,
        "replies_imported": run.replies_imported,
        "videos_failed": run.videos_failed,
    }


@router.get("/comments/sync-status", response_model=CommentSyncStatus)
def comments_sync_status(db: Session = Depends(get_db)):
    settings = get_settings()
    account, channel = _require_connected(db)
    last_run = db.scalar(
        select(SyncRun).where(SyncRun.platform == "youtube_comments", SyncRun.status != "running").order_by(SyncRun.started_at.desc())
    )
    duration = None
    if last_run and last_run.finished_at:
        duration = round((last_run.finished_at - last_run.started_at).total_seconds(), 1)
    return CommentSyncStatus(
        last_synced_at=last_run.finished_at if last_run else None,
        last_sync_status=last_run.status if last_run else None,
        last_sync_duration_seconds=duration,
        last_sync_threads_discovered=last_run.threads_discovered if last_run else None,
        last_sync_comments_imported=last_run.comments_imported if last_run else None,
        last_sync_replies_imported=last_run.replies_imported if last_run else None,
        last_sync_videos_failed=last_run.videos_failed if last_run else None,
        last_sync_error=last_run.error_message if last_run else None,
        automatic_sync_enabled=settings.youtube_sync_enabled,
        automatic_sync_next_at=youtube_scheduler.next_run_at(),
        comments_scope_granted=has_comments_scope(account.scopes),
    )


@router.post("/comments/threads/{thread_platform_id}/reply", response_model=ReplyRead)
def reply_to_thread(thread_platform_id: str, payload: ReplyCreate, db: Session = Depends(get_db)):
    settings = get_settings()
    account, channel = _require_connected(db)
    _require_comments_scope(account)
    client = build_youtube_client(account, settings)
    try:
        comment = post_reply(db, channel, client, thread_platform_id, payload.text)
    except CommentActionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except HttpError as exc:
        raise HTTPException(502, f"YouTube odrzucił publikację odpowiedzi (status {exc.resp.status if exc.resp else '?'}).") from exc
    return _reply_to_read(comment)


@router.put("/comments/{comment_platform_id}", response_model=ReplyRead)
def edit_own_reply(comment_platform_id: str, payload: ReplyUpdate, db: Session = Depends(get_db)):
    settings = get_settings()
    account, channel = _require_connected(db)
    _require_comments_scope(account)
    client = build_youtube_client(account, settings)
    try:
        comment = edit_reply(db, channel, client, comment_platform_id, payload.text)
    except CommentActionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except HttpError as exc:
        raise HTTPException(502, f"YouTube odrzucił edycję odpowiedzi (status {exc.resp.status if exc.resp else '?'}).") from exc
    return _reply_to_read(comment)


@router.delete("/comments/{comment_platform_id}", status_code=204)
def delete_own_reply(comment_platform_id: str, db: Session = Depends(get_db)):
    settings = get_settings()
    account, channel = _require_connected(db)
    _require_comments_scope(account)
    client = build_youtube_client(account, settings)
    try:
        delete_reply(db, channel, client, comment_platform_id)
    except CommentActionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except HttpError as exc:
        raise HTTPException(502, f"YouTube odrzucił usunięcie odpowiedzi (status {exc.resp.status if exc.resp else '?'}).") from exc


# --- Quick reply templates (Part 9) -----------------------------------------


@router.get("/quick-replies", response_model=list[QuickReplyTemplateRead])
def list_quick_replies(db: Session = Depends(get_db)):
    account, _ = _require_connected(db)
    templates = db.scalars(
        select(QuickReplyTemplate).where(QuickReplyTemplate.account_id == account.id).order_by(QuickReplyTemplate.position)
    ).all()
    return [QuickReplyTemplateRead(id=t.id, text=t.text, position=t.position) for t in templates]


@router.post("/quick-replies", response_model=QuickReplyTemplateRead)
def create_quick_reply(payload: QuickReplyTemplateCreate, db: Session = Depends(get_db)):
    account, _ = _require_connected(db)
    text = payload.text.strip()
    if not text:
        raise HTTPException(400, "Treść szablonu nie może być pusta.")
    max_position = db.scalar(select(QuickReplyTemplate).where(QuickReplyTemplate.account_id == account.id).order_by(QuickReplyTemplate.position.desc()))
    template = QuickReplyTemplate(account_id=account.id, text=text, position=(max_position.position + 1) if max_position else 0)
    db.add(template)
    db.commit()
    db.refresh(template)
    return QuickReplyTemplateRead(id=template.id, text=template.text, position=template.position)


@router.put("/quick-replies/{template_id}", response_model=QuickReplyTemplateRead)
def update_quick_reply(template_id: int, payload: QuickReplyTemplateUpdate, db: Session = Depends(get_db)):
    account, _ = _require_connected(db)
    template = db.scalar(select(QuickReplyTemplate).where(QuickReplyTemplate.id == template_id, QuickReplyTemplate.account_id == account.id))
    if template is None:
        raise HTTPException(404, "Nie znaleziono szablonu")
    text = payload.text.strip()
    if not text:
        raise HTTPException(400, "Treść szablonu nie może być pusta.")
    template.text = text
    db.commit()
    db.refresh(template)
    return QuickReplyTemplateRead(id=template.id, text=template.text, position=template.position)


@router.delete("/quick-replies/{template_id}", status_code=204)
def delete_quick_reply(template_id: int, db: Session = Depends(get_db)):
    account, _ = _require_connected(db)
    template = db.scalar(select(QuickReplyTemplate).where(QuickReplyTemplate.id == template_id, QuickReplyTemplate.account_id == account.id))
    if template is None:
        raise HTTPException(404, "Nie znaleziono szablonu")
    db.delete(template)
    db.commit()
