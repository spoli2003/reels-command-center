"""Automatic YouTube sync scheduler (Sprint 6 / Part 5; Release 0.7.0 adds comment sync).

Runs as a single background asyncio task inside the existing backend container —
no extra Docker service, no new infrastructure dependency (see docs/DECISIONS.md
for why an in-process task was chosen over a separate worker service). Disabled by
default (ADR-009): enable via YOUTUBE_SYNC_ENABLED=true /
YOUTUBE_SYNC_INTERVAL_HOURS=<hours, default 6>. Never raises out of the loop —
a failed automatic sync is logged and retried on the next tick, it never crashes
the API process.

Each tick runs video-metric sync, then (if the connected account has granted the
comments scope) an incremental comment sync — the same quota-conscious
recent-vs-full strategy from youtube_comment_sync.py applies automatically, so this
loop doesn't need its own separate cadence for comments.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.integrations.youtube.oauth import has_comments_scope
from app.models.integration import PlatformAccount, YoutubeChannel
from app.services.youtube_client_factory import build_youtube_client
from app.services.youtube_comment_sync import CommentSyncAlreadyRunningError, sync_youtube_comments
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
        client = build_youtube_client(account, settings)
        try:
            channel, _ = sync_youtube(db, account, client)
        except SyncAlreadyRunningError:
            logger.info("Automatyczna synchronizacja pominięta — inna synchronizacja już trwa.")
            channel = None
        except Exception:
            logger.exception("Automatyczna synchronizacja YouTube nie powiodła się.")
            channel = None
        else:
            logger.info("Automatyczna synchronizacja YouTube zakończona pomyślnie.")

        if channel is None:
            channel = db.scalar(select(YoutubeChannel).where(YoutubeChannel.account_id == account.id))
        if channel is None:
            return
        if not has_comments_scope(account.scopes):
            logger.info("Automatyczna synchronizacja komentarzy pominięta — brak uprawnienia youtube.force-ssl (wymaga ponownego połączenia).")
            return
        try:
            sync_youtube_comments(db, channel, client, mode="incremental")
            logger.info("Automatyczna synchronizacja komentarzy zakończona pomyślnie.")
        except CommentSyncAlreadyRunningError:
            logger.info("Automatyczna synchronizacja komentarzy pominięta — inna synchronizacja komentarzy już trwa.")
        except Exception:
            logger.exception("Automatyczna synchronizacja komentarzy nie powiodła się.")
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
