import type { PlatformKey } from "./platform-api";

export type SynchronizationPlatformStatus = {
  platform: PlatformKey;
  connected: boolean;
  configured: boolean;
  display_name: string | null;
  last_synced_at: string | null;
  last_sync_status: string | null;
  last_sync_error: string | null;
  scheduler_enabled: boolean;
  scheduler_interval_hours: number | null;
  next_scheduled_sync_at: string | null;
};

export type SynchronizationHistoryItem = {
  id: number;
  platform: PlatformKey;
  kind: "content" | "comments";
  status: string;
  started_at: string;
  finished_at: string | null;
  imported_items: number;
  items_discovered: number;
  items_processed: number;
  snapshots_created: number;
  comments_imported: number;
  error_message: string | null;
};

export type SynchronizationOverview = {
  platforms: SynchronizationPlatformStatus[];
  history: SynchronizationHistoryItem[];
};

export type GlobalSyncPlatformResult = {
  platform: PlatformKey;
  status: string;
  message: string;
  imported_items: number;
  snapshots_created: number;
  comments_imported: number;
};

export type GlobalSyncResult = {
  status: string;
  started_at: string;
  finished_at: string;
  results: GlobalSyncPlatformResult[];
};
