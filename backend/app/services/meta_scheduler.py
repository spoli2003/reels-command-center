"""Opt-in automatic Facebook + Instagram synchronization (Sprint 0.8.3).

Mirrors the proven YouTube in-process scheduler: disabled by default, one
background task, and the exact same orchestration function as manual/initial
sync. A failed platform never crashes the API or prevents the other platform
from being attempted on the next tick.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.integrations.meta.oauth import (
    FACEBOOK_COMMENT_SYNC_SCOPES,
    FACEBOOK_CONTENT_SYNC_SCOPES,
    INSTAGRAM_COMMENT_SYNC_SCOPES,
    INSTAGRAM_CONTENT_SYNC_SCOPES,
    MetaOAuthError,
    debug_token,
)
from app.models.integration import PlatformAccount
from app.services.content_sync import ContentSyncAlreadyRunningError
from app.services.meta_sync import sync_meta_account
from app.services.token_crypto import decrypt_token

logger = logging.getLogger("meta_scheduler")

_task: Optional[asyncio.Task] = None
last_tick_at: Optional[datetime] = None


def required_sync_scopes(platform: str) -> set[str]:
    if platform == "facebook":
        return set(FACEBOOK_CONTENT_SYNC_SCOPES)
    if platform == "instagram":
        return set(INSTAGRAM_CONTENT_SYNC_SCOPES)
    return set()


def optional_comment_sync_scopes(platform: str) -> set[str]:
    if platform == "facebook":
        return set(FACEBOOK_COMMENT_SYNC_SCOPES - FACEBOOK_CONTENT_SYNC_SCOPES)
    if platform == "instagram":
        return set(INSTAGRAM_COMMENT_SYNC_SCOPES - INSTAGRAM_CONTENT_SYNC_SCOPES)
    return set()


def _run_once_sync() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        accounts = db.scalars(select(PlatformAccount).where(PlatformAccount.platform.in_(["facebook", "instagram"]))).all()
        for account in accounts:
            try:
                token = decrypt_token(account.access_token_encrypted, settings.token_encryption_key)
                info = debug_token(settings, token)
                granted = set(info.get("scopes") or [])
                missing = sorted(required_sync_scopes(account.platform) - granted)
                if not info.get("is_valid", True) or missing:
                    logger.warning(
                        "Automatyczna synchronizacja %s pominięta — token nieważny lub brak uprawnień: %s",
                        account.platform,
                        ", ".join(missing) if missing else "token nieważny",
                    )
                    continue
                account.scopes = ",".join(sorted(granted))
                db.commit()
                missing_comment_scopes = optional_comment_sync_scopes(account.platform) - granted
                result = sync_meta_account(
                    db,
                    account,
                    settings,
                    sync_comments=not missing_comment_scopes,
                    comment_skip_reason=(
                        f"Pominięto komentarze {account.platform}: brak opcjonalnych uprawnień "
                        f"{', '.join(sorted(missing_comment_scopes))}."
                        if missing_comment_scopes
                        else None
                    ),
                )
                logger.info("Automatyczna synchronizacja %s zakończona: %s.", account.platform, result.status)
            except ContentSyncAlreadyRunningError:
                logger.info("Automatyczna synchronizacja %s pominięta — inna synchronizacja już trwa.", account.platform)
            except MetaOAuthError:
                logger.exception("Nie udało się sprawdzić tokenu przed automatyczną synchronizacją %s.", account.platform)
            except Exception:
                logger.exception("Automatyczna synchronizacja %s nie powiodła się.", account.platform)
    finally:
        db.close()


async def _loop() -> None:
    global last_tick_at
    settings = get_settings()
    interval_seconds = max(60.0, settings.meta_sync_interval_hours * 3600)
    while True:
        last_tick_at = datetime.now(timezone.utc)
        try:
            await asyncio.to_thread(_run_once_sync)
        except Exception:
            logger.exception("Nieoczekiwany błąd w pętli harmonogramu Meta.")
        await asyncio.sleep(interval_seconds)


def start() -> None:
    global _task
    settings = get_settings()
    if not settings.meta_sync_enabled:
        logger.info("Automatyczna synchronizacja Meta wyłączona (META_SYNC_ENABLED=false).")
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
    if not settings.meta_sync_enabled or last_tick_at is None:
        return None
    return last_tick_at + timedelta(hours=settings.meta_sync_interval_hours)
