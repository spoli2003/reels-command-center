import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.integrations.youtube.client import YoutubeClient
from app.integrations.youtube.oauth import build_flow, has_comments_scope
from app.models.integration import PlatformAccount, SyncRun, YoutubeMetricSnapshot, YoutubeVideo
from app.schemas.integration import SyncResult, YoutubeStatus, YoutubeVideoRead
from app.schemas.youtube_analytics import ChannelHistoryRead, DataQualityReport, VideoDetailRead, VideoHistoryRead
from app.services import youtube_scheduler
from app.services.token_crypto import encrypt_token
from app.services.youtube_analytics import get_channel, get_channel_history, get_video_detail, get_video_history
from app.services.youtube_client_factory import build_youtube_client
from app.services.youtube_data_quality import audit_youtube_data_quality
from app.services.youtube_intelligence_adapter import compute_all_video_metadata, get_video_history_buckets
from app.services.youtube_sync import SyncAlreadyRunningError, sync_youtube

router = APIRouter(prefix="/api/integrations/youtube", tags=["YouTube"])


@router.get("/status", response_model=YoutubeStatus)
def status(db: Session = Depends(get_db)):
    settings = get_settings()
    configured = settings.client_secrets_path.exists() and bool(settings.token_encryption_key)
    account = db.scalar(select(PlatformAccount).where(PlatformAccount.platform == "youtube"))
    channel = get_channel(db)
    video_count = 0 if channel is None else db.scalar(select(func.count(YoutubeVideo.id)).where(YoutubeVideo.channel_id == channel.id)) or 0

    last_run = db.scalar(
        select(SyncRun).where(SyncRun.platform == "youtube", SyncRun.status != "running").order_by(SyncRun.started_at.desc())
    )
    duration = None
    if last_run and last_run.finished_at:
        duration = round((last_run.finished_at - last_run.started_at).total_seconds(), 1)

    settings_ = get_settings()
    scheduler_enabled = settings_.youtube_sync_enabled
    comments_scope_granted = has_comments_scope(account.scopes) if account else False
    return YoutubeStatus(
        configured=configured,
        connected=account is not None,
        channel_title=channel.title if channel else None,
        channel_id=channel.youtube_channel_id if channel else None,
        last_synced_at=channel.synced_at if channel else None,
        video_count=video_count,
        message="Gotowe do połączenia" if configured and not account else ("Kanał połączony" if account else "Dodaj plik OAuth i klucz szyfrowania"),
        comments_scope_granted=comments_scope_granted,
        comments_reconnect_required=account is not None and not comments_scope_granted,
        last_sync_status=last_run.status if last_run else None,
        last_sync_duration_seconds=duration,
        last_sync_videos_discovered=last_run.videos_discovered if last_run else None,
        last_sync_videos_new=last_run.imported_items if last_run else None,
        last_sync_videos_updated=last_run.videos_updated if last_run else None,
        last_sync_snapshots_created=last_run.snapshots_created if last_run else None,
        last_sync_snapshots_deduplicated=last_run.snapshots_deduplicated if last_run else None,
        last_sync_videos_failed=last_run.videos_failed if last_run else None,
        last_sync_error=last_run.error_message if last_run else None,
        automatic_sync_enabled=scheduler_enabled,
        automatic_sync_interval_hours=settings_.youtube_sync_interval_hours if scheduler_enabled else None,
        automatic_sync_next_at=youtube_scheduler.next_run_at(),
        automatic_sync_note=(
            f"Automatyczna synchronizacja aktywna — co {settings_.youtube_sync_interval_hours:g}h."
            if scheduler_enabled
            else "Automatyczna synchronizacja nie jest jeszcze skonfigurowana — uruchamiaj ją ręcznie."
        ),
    )


@router.get("/connect")
def connect(request: Request):
    settings = get_settings()
    if not settings.token_encryption_key:
        raise HTTPException(500, "Brak TOKEN_ENCRYPTION_KEY w konfiguracji")
    state = secrets.token_urlsafe(32)
    request.session["youtube_oauth_state"] = state
    try:
        flow = build_flow(settings, state=state)
    except FileNotFoundError as exc:
        raise HTTPException(500, str(exc)) from exc
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    request.session["youtube_code_verifier"] = flow.code_verifier
    return RedirectResponse(authorization_url)


@router.get("/callback")
def callback(request: Request, state: str, code: str, db: Session = Depends(get_db)):
    settings = get_settings()
    if state != request.session.pop("youtube_oauth_state", None):
        raise HTTPException(400, "Nieprawidłowy stan OAuth")
    code_verifier = request.session.pop("youtube_code_verifier", None)
    if not code_verifier:
        raise HTTPException(400, "Brak code verifier OAuth. Rozpocznij logowanie ponownie.")
    flow = build_flow(settings, state=state, code_verifier=code_verifier)
    flow.fetch_token(code=code, code_verifier=code_verifier)
    credentials = flow.credentials
    client = YoutubeClient(credentials)
    raw_channel = client.get_my_channel()
    account = db.scalar(select(PlatformAccount).where(PlatformAccount.platform == "youtube", PlatformAccount.external_account_id == raw_channel["id"]))
    if account is None:
        account = PlatformAccount(platform="youtube", external_account_id=raw_channel["id"], display_name=raw_channel.get("snippet", {}).get("title", "YouTube"), access_token_encrypted="")
        db.add(account)
    account.display_name = raw_channel.get("snippet", {}).get("title", account.display_name)
    account.access_token_encrypted = encrypt_token(credentials.token, settings.token_encryption_key)
    if credentials.refresh_token:
        account.refresh_token_encrypted = encrypt_token(credentials.refresh_token, settings.token_encryption_key)
    account.token_expires_at = credentials.expiry
    account.scopes = " ".join(credentials.scopes or [])
    db.commit()
    return RedirectResponse(f"{settings.frontend_url}/?youtube=connected")


@router.post("/sync", response_model=SyncResult)
def sync(db: Session = Depends(get_db)):
    settings = get_settings()
    account = db.scalar(select(PlatformAccount).where(PlatformAccount.platform == "youtube"))
    if account is None:
        raise HTTPException(409, "Najpierw połącz konto YouTube")
    client = build_youtube_client(account, settings)
    try:
        channel, imported = sync_youtube(db, account, client)
    except SyncAlreadyRunningError as exc:
        raise HTTPException(409, str(exc)) from exc
    return SyncResult(imported_videos=imported, channel_title=channel.title, synced_at=channel.synced_at or datetime.now(timezone.utc))


@router.get("/videos", response_model=list[YoutubeVideoRead])
def videos(db: Session = Depends(get_db)):
    items = db.scalars(select(YoutubeVideo).order_by(YoutubeVideo.published_at.desc()).limit(200)).all()
    metadata = compute_all_video_metadata(db)
    result: list[YoutubeVideoRead] = []
    for item in items:
        latest = db.scalar(select(YoutubeMetricSnapshot).where(YoutubeMetricSnapshot.video_id == item.id).order_by(YoutubeMetricSnapshot.captured_at.desc()).limit(1))
        result.append(YoutubeVideoRead(
            youtube_video_id=item.youtube_video_id,
            title=item.title,
            published_at=item.published_at,
            thumbnail_url=item.thumbnail_url,
            duration_seconds=item.duration_seconds,
            is_short_candidate=item.is_short_candidate,
            views=latest.views if latest else 0,
            likes=latest.likes if latest else 0,
            comments=latest.comments if latest else 0,
            **metadata.get(item.youtube_video_id, {}),
        ))
    return result


@router.delete("/disconnect", status_code=204)
def disconnect(db: Session = Depends(get_db)):
    accounts = db.scalars(select(PlatformAccount).where(PlatformAccount.platform == "youtube")).all()
    for account in accounts:
        db.delete(account)
    db.commit()


@router.get("/videos/{youtube_video_id}", response_model=VideoDetailRead)
def video_detail(youtube_video_id: str, db: Session = Depends(get_db)):
    detail = get_video_detail(db, youtube_video_id)
    if detail is None:
        raise HTTPException(404, "Nie znaleziono filmu")
    metadata = compute_all_video_metadata(db)
    detail.update(metadata.get(youtube_video_id, {}))
    return detail


@router.get("/videos/{youtube_video_id}/history", response_model=VideoHistoryRead)
def video_history(youtube_video_id: str, db: Session = Depends(get_db)):
    history = get_video_history(db, youtube_video_id)
    if history is None:
        raise HTTPException(404, "Nie znaleziono filmu")
    buckets = get_video_history_buckets(db, youtube_video_id)
    return VideoHistoryRead(points=history, **(buckets or {"granularity": "daily", "buckets": [], "insufficient": True}))


@router.get("/channel/history", response_model=ChannelHistoryRead)
def channel_history(db: Session = Depends(get_db)):
    result = get_channel_history(db)
    if result is None:
        raise HTTPException(404, "Brak połączonego kanału")
    return result


@router.get("/data-quality", response_model=DataQualityReport)
def data_quality(db: Session = Depends(get_db)):
    return audit_youtube_data_quality(db)
    return history
