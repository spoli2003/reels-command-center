from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.integration import PlatformAccount, SyncRun, YoutubeChannel
from app.schemas.synchronization import (
    GlobalSyncResult,
    SynchronizationHistoryItem,
    SynchronizationOverview,
    SynchronizationPlatformStatus,
)
from app.services import meta_scheduler, youtube_scheduler
from app.services.global_sync import sync_all_connected

router = APIRouter(prefix="/api/synchronization", tags=["Synchronization"])
STALE_RUN_MINUTES = 30


def _base_platform(value: str) -> str:
    return value.removesuffix("_comments")


@router.get("", response_model=SynchronizationOverview)
def overview(history_limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)):
    stale_before = datetime.now(timezone.utc) - timedelta(minutes=STALE_RUN_MINUTES)
    stale_runs = db.scalars(
        select(SyncRun).where(SyncRun.status == "running", SyncRun.started_at < stale_before)
    ).all()
    for stale_run in stale_runs:
        stale_run.status = "failed"
        stale_run.finished_at = datetime.now(timezone.utc)
        stale_run.error_message = "Przerwana — synchronizacja nie raportowała postępu przez ponad 30 minut."
    if stale_runs:
        db.commit()
    settings = get_settings()
    accounts = {item.platform: item for item in db.scalars(select(PlatformAccount)).all()}
    platforms: list[SynchronizationPlatformStatus] = []

    for platform in ("youtube", "facebook", "instagram"):
        account = accounts.get(platform)
        last_run = db.scalar(
            select(SyncRun)
            .where(SyncRun.platform == platform, SyncRun.status != "running")
            .order_by(SyncRun.started_at.desc())
        )
        running_run = db.scalar(
            select(SyncRun)
            .where(SyncRun.platform == platform, SyncRun.status == "running")
            .order_by(SyncRun.started_at.desc())
        )
        if platform == "youtube":
            channel = db.scalar(select(YoutubeChannel).order_by(YoutubeChannel.id.asc()))
            configured = settings.client_secrets_path.exists() and bool(settings.token_encryption_key)
            last_synced_at = channel.synced_at if channel else (last_run.finished_at if last_run else None)
            scheduler_enabled = settings.youtube_sync_enabled
            interval = settings.youtube_sync_interval_hours if scheduler_enabled else None
            next_run = youtube_scheduler.next_run_at()
        else:
            configured = bool(settings.meta_app_id and settings.meta_app_secret and settings.token_encryption_key)
            last_synced_at = last_run.finished_at if last_run else None
            scheduler_enabled = settings.meta_sync_enabled
            interval = settings.meta_sync_interval_hours if scheduler_enabled else None
            next_run = meta_scheduler.next_run_at()

        platforms.append(
            SynchronizationPlatformStatus(
                platform=platform,
                connected=account is not None,
                configured=configured,
                display_name=account.display_name if account else None,
                last_synced_at=last_synced_at,
                last_sync_status="running" if running_run else (last_run.status if last_run else None),
                last_sync_error=last_run.error_message if last_run else None,
                scheduler_enabled=scheduler_enabled,
                scheduler_interval_hours=interval,
                next_scheduled_sync_at=next_run,
            )
        )

    runs = db.scalars(select(SyncRun).order_by(SyncRun.started_at.desc()).limit(history_limit)).all()
    history = [
        SynchronizationHistoryItem(
            id=run.id,
            platform=_base_platform(run.platform),
            kind="comments" if run.platform.endswith("_comments") else "content",
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            imported_items=run.imported_items,
            items_discovered=run.videos_discovered,
            items_processed=(
                min(run.videos_discovered, run.videos_updated)
                if run.platform.endswith("_comments")
                else min(run.videos_discovered, run.videos_updated + run.imported_items + run.videos_failed)
            ),
            snapshots_created=run.snapshots_created,
            comments_imported=run.comments_imported,
            error_message=run.error_message,
        )
        for run in runs
    ]
    return SynchronizationOverview(platforms=platforms, history=history)


@router.post("/sync-all", response_model=GlobalSyncResult)
def sync_all(db: Session = Depends(get_db)):
    return sync_all_connected(db, get_settings())
