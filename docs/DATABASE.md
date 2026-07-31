# Database Model

This document describes RCC's data entities in prose — for exact column definitions,
read the SQLAlchemy models under `backend/app/models/`. Migrations live under
`backend/alembic/versions/` and are applied automatically on container start.

## Current entities

### User
Registration/login identity (email, hashed password). Built (Argon2 hashing, JWT
cookie session) but **not currently enforced on any route** — RCC is single-tenant in
practice today; every resource below is global, not scoped to a user.

### PlatformAccount
One connected third-party account (currently only `platform = "youtube"`). Holds
encrypted OAuth tokens and scopes. A future Facebook/Instagram/TikTok connection would
add rows here with a different `platform` value, reusing the same table.

### YoutubeChannel
The channel behind a connected `PlatformAccount`: title, thumbnail, uploads playlist
id, and the **current** subscriber/view/video counts (a snapshot of "now," not
history).

### YoutubeChannelSnapshot
One row per sync run: `captured_at`, `subscriber_count`, `view_count`, `video_count`.
This is where channel-level *history* lives — introduced in Sprint 4 specifically so
subscriber growth could be tracked over time. Only accumulates from the moment it was
introduced; no retroactive backfill is possible for periods before it existed.

### YoutubeVideo
One row per video on a channel: title, description, published date, duration,
thumbnail, short-form flag. Metadata that rarely changes — deliberately separate from
performance data (see below) so history can accumulate without rewriting the video's
identity row.

### YoutubeMetricSnapshot
One row per video per sync run: `captured_at`, `views`, `likes`, `comments`.
**Immutable and append-only** — never updated in place, only inserted, and never
deleted except by the Sprint 6 data-quality audit's narrowly-scoped exact-duplicate
repair (see below). This is what makes velocity/trend/growth analysis possible: a
video's performance is a time series, not a single mutable number. There is no
database-level uniqueness constraint on `(video_id, captured_at)` — dedup is an
application-level time-window check in `youtube_sync.py` instead (see ADR-014 in
[DECISIONS.md](./DECISIONS.md)): a new snapshot is skipped if the same video already
has one younger than 5 minutes, which is how the sync engine stays idempotent against
an accidental double-invocation without ever discarding a legitimate "unchanged since
last sync" data point.

### SyncRun
One row per sync attempt: platform, status (`running`/`success`/`partial`/`failed`),
start/finish time, `videos_discovered`, `videos_updated`, `snapshots_created` (since
Sprint 4.1), and — since Sprint 6 — `snapshots_deduplicated` (snapshots skipped as
duplicates, see above) and `videos_failed` (videos whose processing raised inside
their own SQL savepoint without rolling back the rest of the run; `status` becomes
`"partial"`, never silently `"success"`, whenever this is nonzero). This is the audit
trail behind the "sync is actually doing something" visibility fixed in Sprint 4.1
and extended in Sprint 6. Release 0.7.0 added `threads_discovered`/
`comments_imported`/`replies_imported`, populated only on `platform="youtube_comments"`
rows — one shared table, discriminated by `platform`, rather than a parallel table
per sync type (see ADR-018).

### YoutubeCommentThread *(Release 0.7.0)*
One row per top-level comment thread on a tracked video: the top-level comment's
own author/text/like/date fields live directly on this row (mirroring the YouTube
Data API's `commentThreads` resource, which embeds the top-level comment in its own
snippet), plus `total_reply_count`, `moderation_status`, `can_reply`. **Upsert-only**
— a thread is never deleted just because a later sync temporarily omits it (API
hiccups, moderation review). `platform_thread_id` is the natural upsert key.

### YoutubeComment *(Release 0.7.0)*
One row per **reply** — YouTube comments are a flat, two-level structure (no
nested replies-of-replies), so `parent_comment_id` always points back to the
thread's `top_level_comment_id`. The top-level comment's content is NOT duplicated
here; it lives only on `YoutubeCommentThread` (see above). `is_own_reply` is set
when `author_channel_id` matches the connected channel — this is what "answered"
means (a thread with ≥1 reply where `is_own_reply=True`) and what authorizes
editing/deleting (only the exact row the connected channel authored). Upsert-only
from sync; explicitly deleting a reply through RCC's UI **does** remove the row —
see ADR-018 for the distinction between sync-time upsert and user-initiated
deletion.

### QuickReplyTemplate *(Release 0.7.0)*
Locally managed reply snippets, scoped by `account_id` (RCC is single-tenant
today — see ADR-010 for the future `Workspace` scoping plan). Selecting one into
the reply composer never sends it automatically.

### Reel *(legacy, disconnected)*
An early "content idea" concept (title, category, hook) predating the unified content
engine below. Not linked to any other entity, not used by any current page. Left in
place rather than removed mid-project; a candidate for deletion once confirmed
unneeded.

### ContentVideo / Publication / MetricSnapshot *(unified engine, live since Release 0.8.0)*
Designed in Sprint 1 as a cross-platform aggregation layer: one canonical
`ContentVideo` can have many `Publication` rows (one per platform upload), each with
its own `MetricSnapshot` history. Populated for real as of Release 0.8.0 (ADR-020):
Facebook and Instagram sync directly into it via `content_sync.py`, and YouTube's
own dedicated pipeline (still the source of truth for its own tables) additively
dual-writes into it via `youtube_unified_bridge.py` after every sync, so all three
platforms are visible through the generic `/api/platforms/*` API and `/platforms/*`
frontend surface.

### ContentCommentThread / ContentComment *(unified engine, live since Release 0.8.0)*
The generic equivalent of `YoutubeCommentThread`/`YoutubeComment` (ADR-020),
FK'd to `Publication` instead of `YoutubeVideo` so Facebook and Instagram
comments share one storage/query/sync/action implementation with each other,
reusing `comment_intelligence.py` (conversation state, priority scoring)
unchanged. YouTube's own comment tables remain the source of truth for its own
Community Inbox; `youtube_unified_bridge.py` additively mirrors them here too.

## Relationships (current, YouTube path)

```
PlatformAccount (1) ──── (1) YoutubeChannel ──┬── (many) YoutubeChannelSnapshot
                                                └── (many) YoutubeVideo ──┬── (many) YoutubeMetricSnapshot
                                                                          └── (many) YoutubeCommentThread ──── (many) YoutubeComment
PlatformAccount (1) ──── (many) QuickReplyTemplate
SyncRun — not foreign-keyed to any of the above; correlated by platform + timestamp only.
```

## Relationships (current, unified engine path — Facebook/Instagram + bridged YouTube)

```
PlatformAccount (1) ──── (many) Publication ──── (1) ContentVideo
                                    │
                                    ├── (many) MetricSnapshot
                                    └── (many) ContentCommentThread ──── (many) ContentComment
```
No generic `Channel` entity exists yet (see "Channel (generic)" below) — a
Facebook Page or Instagram professional account IS its `PlatformAccount` row
directly, one level shallower than YouTube's `PlatformAccount` → `YoutubeChannel`.

## Future entities (planned, not yet modeled)

### Workspace
Would wrap one or more `PlatformAccount` rows under a user/team, enabling real
multi-tenancy. Every query in every service would need to add a workspace scope.

### Platform (generic)
Today, "platform" is just a string column on `PlatformAccount`/`Publication`. A
cleaner future model could promote this to its own table (name, capabilities,
supported metrics) once a second real integration exists and the differences between
platforms need to be queried, not just stored as a label.

### Channel (generic)
The unified-engine equivalent of `YoutubeChannel` — currently only YouTube has a
first-class channel entity; a generic one would let the unified `ContentVideo` model
actually aggregate across platforms.

### Video (generic)
~~`ContentVideo` already exists for this purpose (see above) — the future work here
is population, not schema.~~ Done as of Release 0.8.0 — see above.

### Snapshot (generic)
~~`MetricSnapshot` (unified engine) already exists in parallel to
`YoutubeMetricSnapshot` — the future work is making the YouTube sync path write to
both, or migrating fully to one.~~ Done as of Release 0.8.0, via the additive
`youtube_unified_bridge.py` dual-write — see above. `YoutubeMetricSnapshot`
remains the source of truth for YouTube's own dedicated pipeline; nothing was
migrated away from it.

### Analytics
Currently computed on-demand (no materialized analytics tables). If computation cost
ever becomes a concern at scale, a cached/materialized analytics table keyed by
video + date could be introduced — not needed at RCC's current single-channel scale.

### AI
Would need a table (or cache) for AI-narrated recommendations if their generation
becomes expensive enough to want to store rather than recompute per request. No design
work done yet — see [AI_ENGINE.md](./AI_ENGINE.md).

### CRM
Not designed. Would eventually link `ContentVideo`/topics to leads or clients for
creators running content as part of a business funnel.
