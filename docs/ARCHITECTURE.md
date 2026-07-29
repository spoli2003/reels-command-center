# Architecture

## Conceptual data flow

```
Workspace
   ↓
Platforms       (YouTube today; Facebook / Instagram / TikTok planned)
   ↓
Channels        (one connected account per platform)
   ↓
Videos          (canonical content items on that channel)
   ↓
Historical Snapshots   (immutable point-in-time metric captures)
   ↓
Analytics       (derived metrics: views/day, engagement rate, ratios)
   ↓
Creator Intelligence   (confidence-gated, explainable recommendations)
   ↓
AI Engine       (not yet built — narrates the layers above, invents nothing)
   ↓
CRM             (not yet built — links content performance to leads/clients)
```

**Where this stands today:** everything from Platforms down through Creator
Intelligence is implemented for YouTube. Workspace (multi-tenancy), AI Engine, and CRM
are future layers — see below and [TODO.md](./TODO.md).

### Workspace (future)

Not implemented. RCC is currently single-tenant: one set of connected accounts, no
user-scoped data isolation beyond the (currently unused) `User`/auth model. A future
Workspace layer would wrap one or more `PlatformAccount` rows per user/team and scope
every query below it.

### Platforms → Channels

`PlatformAccount` (OAuth credentials, one row per connected account) →
`YoutubeChannel` (channel identity + current stats: subscriber/view/video count).
Platform-specific today; a Facebook/Instagram/TikTok integration would add its own
`*Account`/`*Channel`-shaped tables following the same pattern, not modify these.

### Videos → Historical Snapshots

`YoutubeVideo` (title, description, published date, duration, thumbnail — metadata
that rarely changes) is separated from `YoutubeMetricSnapshot` (views/likes/comments
at a captured point in time — one row per video per sync, immutable, never updated in
place) and `YoutubeChannelSnapshot` (channel-level subscriber/view/video counts, one
row per sync). This separation is what makes trend/velocity analysis possible: a
video's metadata is a single row, its performance over time is an append-only log.

### Analytics

`backend/app/services/youtube_analytics.py` — per-video and channel-level derived
metrics (views/day, engagement rate, channel views/day normalized by the age of the
*oldest tracked video*, never by YouTube account age). Also owns channel-level
history bucketing (`get_channel_history`) and the [data-quality audit](#data-quality-audit)
below.

#### History bucketing (Sprint 6)

Both video history (`content_metrics.bucket_history`, platform-agnostic) and channel
history (`youtube_analytics.get_channel_history`, YouTube-specific) group raw,
irregularly-spaced snapshots into age-anchored periods instead of plotting raw
synchronization timestamps — see ADR-013 in [DECISIONS.md](./DECISIONS.md) for why.
Rule: under 30 days since the anchor (a video's publish date; a channel's first
tracked snapshot) → one point per day; 30–180 days → one point per week; beyond 180
days → one point per month. Each period's value is its *last* snapshot (cumulative
counters, so this is a closing value, like a daily candle) via the bucketing
function, exposed at `GET /videos/{id}/history` (`points` + `buckets` +
`granularity` + `insufficient`) and `GET /channel/history`.

#### Data-quality audit

`youtube_data_quality.audit_youtube_data_quality` (`GET
/api/integrations/youtube/data-quality`) checks for exact-duplicate snapshots
(auto-repaired — see ADR-014), impossible timestamps (a snapshot dated before the
video's publish date), and non-monotonic view drops (reported only, never
"corrected" — YouTube itself occasionally removes spam views after the fact, which
is a legitimate external event, not RCC data corruption).

### Creator Intelligence

`backend/app/services/intelligence/` — **platform-agnostic by design**. Nothing in
this package imports a YouTube model:

```
intelligence/
  types.py            ContentItem, DerivedItem, Recommendation, Confidence, Trend
  content_metrics.py  derive age/views-per-day/engagement/velocity/trend/score/label
  topics.py            Polish tokenizer + keyword-stem clustering (no ML)
  title_patterns.py    rule-based title pattern detectors
  engine.py             daily brief, winning/attention videos, publishing patterns,
                         follow-up opportunities, content recommendations
```

`youtube_intelligence_adapter.py` is the **only** YouTube-specific file in this path:
it converts `YoutubeVideo` + snapshot rows into `ContentItem`, calls the engine, and
re-attaches display fields (title, thumbnail) for the API response. A future
Facebook/Instagram/TikTok adapter is the same shape — nothing under `intelligence/`
would change.

### AI Engine (future)

See [AI_ENGINE.md](./AI_ENGINE.md). Sits strictly downstream of Creator Intelligence,
consuming its structured `Recommendation` objects to produce natural-language
narration — never generating its own numbers.

### CRM (future)

Not designed yet. Intended to eventually link content performance (which videos, which
topics) to business outcomes (leads, clients) for creators who run content as a
funnel.

## Backend structure

```
backend/app/
  api/            FastAPI routers — thin, no business logic
  schemas/        Pydantic request/response contracts
  services/       business logic (sync, analytics, intelligence engine, adapters)
  models/         SQLAlchemy ORM
  integrations/   third-party API clients (YouTube Data API v3 OAuth + client)
  core/           settings, security (JWT/Argon2 — built, not wired to any route)
  db/             engine/session/declarative base
```

Layering rule: routers call services, services call models — routers never touch
SQLAlchemy directly for anything beyond simple lookups, and the intelligence engine
never imports a model at all (see above).

## Frontend structure

```
frontend/
  app/            Next.js App Router pages — server components, fetch on the server
  components/     shared UI (AppShell, PlatformSubNav, StatCard, RankedVideoList,
                  chart primitives, compare/*, intelligence widgets)
  lib/             youtube-api.ts (typed fetch client), youtube-metrics.ts (client-side
                  derived metrics, filtering, sorting, scoring — mirrors backend formulas
                  where both layers need the same number)
```

Server components fetch data (no client-side loading spinners for initial render);
client components (`"use client"`) exist only where interactivity is required
(filters, sort, forms, the video comparison picker).

## Scheduler & automation

Implemented in Sprint 6 as `backend/app/services/youtube_scheduler.py` — a single
`asyncio` background task started from the FastAPI `lifespan` hook in `main.py`, not
a separate Docker service (see ADR-015 for why). Configuration:
`YOUTUBE_SYNC_ENABLED` (default `false`) and `YOUTUBE_SYNC_INTERVAL_HOURS` (default
`6`). Disabled by default per ADR-009 — an operator must explicitly opt in. The
scheduler reuses the exact same `sync_youtube()` function and overlap/dedup guards as
the manual `POST /api/integrations/youtube/sync` endpoint (see below), so there is
only one sync code path regardless of trigger.

Sync itself (`backend/app/services/youtube_sync.py`) is idempotent and
crash-tolerant:
- **Overlap guard**: a sync request while another is genuinely `"running"` for the
  same platform is rejected (`409`) rather than allowed to race.
- **Stale-run reclaim**: a `"running"` row older than 30 minutes is treated as an
  orphan from a crash/restart, marked `"failed"`, and a new sync is allowed to
  proceed — this is what makes "recover correctly after restart" true without any
  manual intervention.
- **Per-video fault isolation**: each video is processed inside its own SQL
  savepoint (`db.begin_nested()`); one bad API response marks that video failed and
  the run continues, so `status` becomes `"partial"` (never falsely `"success"`)
  instead of losing every other video's already-processed data.
- **Snapshot dedup**: see ADR-014.

Every sync run records `videos_discovered`/`videos_updated`/`snapshots_created`/
`snapshots_deduplicated`/`videos_failed`/duration/errors on `SyncRun`, and one
`YoutubeChannelSnapshot` per run, so sync effects are fully auditable — surfaced in
the UI's sync panel including automatic-scheduler status and the next planned run.

## Integrations

- **YouTube Data API v3** (`google-api-python-client` + `google-auth-oauthlib`, PKCE
  OAuth flow). Provides channel/video metadata and `viewCount`/`likeCount`/
  `commentCount` only.
- **YouTube Analytics API** — not integrated. Shares, watch time, average view
  duration, CTR, impressions, traffic sources, and per-video subscriber attribution
  all require this separate API and different OAuth scopes. RCC is honest about this
  gap in the UI rather than fabricating these numbers (see
  [UI_GUIDELINES.md](./UI_GUIDELINES.md)).

## Future multi-workspace support

Adding real multi-tenancy would mean: a `Workspace` model, `PlatformAccount` gaining a
`workspace_id`, every service-layer query scoping by workspace, and wiring the
already-built (but currently unused) JWT/cookie auth into every route. None of this is
started — RCC today is single-tenant by omission, not by explicit single-tenant
design, so this is additive rather than a rewrite when it happens.
