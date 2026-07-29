import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.integrations.youtube.client import YoutubeClient, credentials_from_tokens
from app.integrations.youtube.oauth import build_flow
from app.models.integration import PlatformAccount, YoutubeChannel, YoutubeMetricSnapshot, YoutubeVideo
from app.schemas.integration import SyncResult, YoutubeStatus, YoutubeVideoRead
from app.services.token_crypto import decrypt_token, encrypt_token
from app.services.youtube_sync import sync_youtube

router = APIRouter(prefix="/api/integrations/youtube", tags=["YouTube"])


def _oauth_client_data(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("web") or data.get("installed") or {}


@router.get("/status", response_model=YoutubeStatus)
def status(db: Session = Depends(get_db)):
    settings = get_settings()
    configured = settings.client_secrets_path.exists() and bool(settings.token_encryption_key)
    account = db.scalar(select(PlatformAccount).where(PlatformAccount.platform == "youtube"))
    channel = None if account is None else db.scalar(select(YoutubeChannel).where(YoutubeChannel.account_id == account.id))
    video_count = 0 if channel is None else db.scalar(select(func.count(YoutubeVideo.id)).where(YoutubeVideo.channel_id == channel.id)) or 0
    return YoutubeStatus(
        configured=configured,
        connected=account is not None,
        channel_title=channel.title if channel else None,
        channel_id=channel.youtube_channel_id if channel else None,
        last_synced_at=channel.synced_at if channel else None,
        video_count=video_count,
        message="Gotowe do połączenia" if configured and not account else ("Kanał połączony" if account else "Dodaj plik OAuth i klucz szyfrowania"),
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
    data = _oauth_client_data(settings.client_secrets_path)
    credentials = credentials_from_tokens(
        decrypt_token(account.access_token_encrypted, settings.token_encryption_key),
        decrypt_token(account.refresh_token_encrypted, settings.token_encryption_key) if account.refresh_token_encrypted else None,
        data["client_id"],
        data["client_secret"],
        data.get("token_uri", "https://oauth2.googleapis.com/token"),
    )
    channel, imported = sync_youtube(db, account, YoutubeClient(credentials))
    return SyncResult(imported_videos=imported, channel_title=channel.title, synced_at=channel.synced_at or datetime.now(timezone.utc))


@router.get("/videos", response_model=list[YoutubeVideoRead])
def videos(db: Session = Depends(get_db)):
    items = db.scalars(select(YoutubeVideo).order_by(YoutubeVideo.published_at.desc()).limit(200)).all()
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
        ))
    return result


@router.delete("/disconnect", status_code=204)
def disconnect(db: Session = Depends(get_db)):
    accounts = db.scalars(select(PlatformAccount).where(PlatformAccount.platform == "youtube")).all()
    for account in accounts:
        db.delete(account)
    db.commit()
