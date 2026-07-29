"""Automatic YouTube sync scheduler (Sprint 6 / Part 5).

Runs as a single background asyncio task inside the existing backend container —
no extra Docker service, no new infrastructure dependency (see docs/DECISIONS.md
for why an in-process task was chosen over a separate worker service). Disabled by
default (ADR-009): enable via YOUTUBE_SYNC_ENABLED=true /
YOUTUBE_SYNC_INTERVAL_HOURS=<hours, default 6>. Never raises out of the loop —
a failed automatic sync is logged and retried on the next tick, it never crashes
the API process.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.integrations.youtube.client import YoutubeClient, credentials_from_tokens
from app.integrations.youtube.oauth import load_client_secrets
from app.models.integration import PlatformAccount
from app.services.token_crypto import decrypt_token
from app.services.youtube_sync import SyncAlreadyRunningError, sync_youtube

logger = logging.getLogger("youtube_scheduler")

_task: Optional[asyncio.Task] = None
last_tick_at: Optional[datetime] = None


def _run_once_sync() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        account = db.scalar(select(PlatformAccount).where(PlatformAccount.platform == "youtube"))
        if account is None:
            logger.info("Automatyczna synchronizacja pominięta — brak połączonego konta YouTube.")
            return
        data = load_client_secrets(settings.client_secrets_path)
        credentials = credentials_from_tokens(
            decrypt_token(account.access_token_encrypted, settings.token_encryption_key),
            decrypt_token(account.refresh_token_encrypted, settings.token_encryption_key) if account.refresh_token_encrypted else None,
            data["client_id"],
            data["client_secret"],
            data.get("token_uri", "https://oauth2.googleapis.com/token"),
        )
        sync_youtube(db, account, YoutubeClient(credentials))
        logger.info("Automatyczna synchronizacja YouTube zakończona pomyślnie.")
    except SyncAlreadyRunningError:
        logger.info("Automatyczna synchronizacja pominięta — inna synchronizacja już trwa.")
    except Exception:
        logger.exception("Automatyczna synchronizacja YouTube nie powiodła się.")
    finally:
        db.close()


async def _loop() -> None:
    global last_tick_at
    settings = get_settings()
    interval_seconds = max(60.0, settings.youtube_sync_interval_hours * 3600)
    while True:
        last_tick_at = datetime.now(timezone.utc)
        try:
            await asyncio.to_thread(_run_once_sync)
        except Exception:
            logger.exception("Nieoczekiwany błąd w pętli harmonogramu synchronizacji YouTube.")
        await asyncio.sleep(interval_seconds)


def start() -> None:
    global _task
    settings = get_settings()
    if not settings.youtube_sync_enabled:
        logger.info("Automatyczna synchronizacja YouTube wyłączona (YOUTUBE_SYNC_ENABLED=false).")
        return
    if _task is not None and not _task.done():
        return
    _task = asyncio.ensure_future(_loop())


async def stop() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except (asyncio.CancelledError, Exception):
        pass
    _task = None


def next_run_at() -> Optional[datetime]:
    settings = get_settings()
    if not settings.youtube_sync_enabled or last_tick_at is None:
        return None
    return last_tick_at + timedelta(hours=settings.youtube_sync_interval_hours)
