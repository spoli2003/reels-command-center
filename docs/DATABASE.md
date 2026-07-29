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
**Immutable and append-only** — never updated in place, only inserted. This is what
makes velocity/trend/growth analysis possible: a video's performance is a time series,
not a single mutable number.

### SyncRun
One row per sync attempt: platform, status (`running`/`success`/`partial`/`failed`),
start/finish time, and (since Sprint 4.1) `videos_discovered`, `videos_updated`,
`snapshots_created`, plus any error message. This is the audit trail behind the
"sync is actually doing something" visibility fixed in Sprint 4.1.

### Reel *(legacy, disconnected)*
An early "content idea" concept (title, category, hook) predating the unified content
engine below. Not linked to any other entity, not used by any current page. Left in
place rather than removed mid-project; a candidate for deletion once confirmed
unneeded.

### ContentVideo / Publication / MetricSnapshot *(unified engine, currently unused)*
Designed in Sprint 1 as a cross-platform aggregation layer: one canonical
`ContentVideo` can have many `Publication` rows (one per platform upload), each with
its own `MetricSnapshot` history. **The YouTube sync path never writes to this model**
— it remains a real, working API surface (`/api/content/*`) with zero rows in
practice. This is the intended home for genuine cross-platform aggregation once a
second platform integration exists; see [ROADMAP.md](./ROADMAP.md) and
[TODO.md](./TODO.md).

## Relationships (current, YouTube path)

```
PlatformAccount (1) ──── (1) YoutubeChannel ──┬── (many) YoutubeChannelSnapshot
                                                └── (many) YoutubeVideo ──── (many) YoutubeMetricSnapshot
SyncRun — not foreign-keyed to any of the above; correlated by platform + timestamp only.
```

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
`ContentVideo` already exists for this purpose (see above) — the future work here is
population, not schema.

### Snapshot (generic)
`MetricSnapshot` (unified engine) already exists in parallel to
`YoutubeMetricSnapshot` — the future work is making the YouTube sync path write to
both, or migrating fully to one.

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
