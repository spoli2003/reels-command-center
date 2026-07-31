from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SynchronizationPlatformStatus(BaseModel):
    platform: str
    connected: bool
    configured: bool
    display_name: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    last_sync_error: Optional[str] = None
    scheduler_enabled: bool = False
    scheduler_interval_hours: Optional[float] = None
    next_scheduled_sync_at: Optional[datetime] = None


class SynchronizationHistoryItem(BaseModel):
    id: int
    platform: str
    kind: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    imported_items: int = 0
    items_discovered: int = 0
    items_processed: int = 0
    snapshots_created: int = 0
    comments_imported: int = 0
    error_message: Optional[str] = None


class SynchronizationOverview(BaseModel):
    platforms: list[SynchronizationPlatformStatus]
    history: list[SynchronizationHistoryItem] = Field(default_factory=list)


class GlobalSyncPlatformResult(BaseModel):
    platform: str
    status: str
    message: str
    imported_items: int = 0
    snapshots_created: int = 0
    comments_imported: int = 0


class GlobalSyncResult(BaseModel):
    status: str
    started_at: datetime
    finished_at: datetime
    results: list[GlobalSyncPlatformResult]
