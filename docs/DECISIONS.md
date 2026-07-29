# Architecture & Product Decision Record

This file records every important architectural and product decision made on RCC, in
the order they were made. It is the single source of truth when two documents seem to
disagree — if `ARCHITECTURE.md` or `UI_GUIDELINES.md` ever contradicts an entry here,
this file wins and the other document should be corrected.

**Process:** after every sprint, append new decisions here if any were made (a sprint
can complete with zero new entries — this file records *decisions*, not activity).
Never edit or delete a past entry to make it look retroactively different; if a
decision is reversed, add a new entry that supersedes it and say so explicitly.

Format: **Decision** / Context / Consequences.

---

### ADR-001 — RCC is a Content Operating System, not an analytics dashboard
**Context:** Early sprints risked drifting toward "add another chart" as the default
response to every request.
**Decision:** Every screen must answer *what happened, why, what deserves attention,
what to do next* — not just display numbers. Statistics are a means, not the product.
**Consequences:** Any proposed feature that only adds data without a conclusion is
rejected or reshaped. See [PRODUCT_VISION.md](./PRODUCT_VISION.md).

### ADR-002 — Video is the primary entity of the application
**Context:** RCC aggregates channel-, topic-, and platform-level views, but all of
them are derived from individual pieces of content.
**Decision:** The video (generically, a `ContentItem`) is the atomic unit everything
else is computed from — channel stats, topics, publishing patterns, and recommendations
are all aggregations *over* videos, never a separate first-class concept computed
independently.
**Consequences:** New analytics should be added as a function over
`list[DerivedItem]` before being added as a bespoke channel-level query.

### ADR-003 — The unified content engine is kept, not populated, until a second platform exists
**Context:** Sprint 1 built `ContentVideo`/`Publication`/`MetricSnapshot` for
cross-platform aggregation. The YouTube sync path was never wired to populate it.
**Decision:** Leave the model and its `/api/content/*` endpoints in place and
documented rather than deleting them mid-project or forcing YouTube data into it
prematurely. It becomes the real aggregation layer once a second platform integration
exists (see ADR-007).
**Consequences:** `/videos` (Library) and the dashboard read YouTube-specific tables
directly today; this is expected, not a bug, until a second platform lands.

### ADR-004 — Never fabricate data; show honest "unavailable" states instead
**Context:** Repeated temptation across sprints to fill an empty chart or a missing
metric with a plausible-looking placeholder.
**Decision:** Any metric or chart with insufficient or unavailable data shows an
explicit, specific explanation of why and (where relevant) what to do about it.
**Consequences:** Sprint 5's "not currently available" card for shares/watch-time/CTR/
impressions/traffic-sources/subscriber-attribution exists because of this rule, not in
spite of it — those metrics require the YouTube Analytics API, which RCC does not
integrate.

### ADR-005 — Performance scores are always relative to a stated scope, never universal
**Context:** An early version of the composite score risked being read as an absolute,
permanent judgment of a video.
**Decision:** Every displayed score explicitly states what it's relative to (the
current filter, the whole channel, or a comparison set) in its label/tooltip.
**Consequences:** The same video can show different scores in different contexts
(dashboard filter vs. channel-wide) and this is correct, not inconsistent — as long as
the scope is labeled.

### ADR-006 — Charts exist only when they improve creator decisions
**Context:** A views-vs-likes scatter plot and a raw upload-frequency bar chart shipped
in early sprints, then were removed in Sprint 4.1 once nothing on the page changed
what a creator would do based on them.
**Decision:** Before adding a chart, name the specific creator decision it improves.
If a ranking, a stat, or a sentence would serve that decision better, use that instead.
**Consequences:** RCC intentionally has fewer charts today than it did after Sprint 4 —
this is a feature of the design process, not a gap.

### ADR-007 — The Creator Intelligence engine is platform-agnostic by construction
**Context:** Built in Sprint 4 with Facebook/Instagram/TikTok explicitly in mind.
**Decision:** `backend/app/services/intelligence/` may never import a YouTube-specific
model. All platform-specific logic (converting stored rows into the generic
`ContentItem` shape) lives in a thin adapter module
(`youtube_intelligence_adapter.py`) — one per platform.
**Consequences:** Adding Facebook/Instagram/TikTok (see [TODO.md](./TODO.md)) means
writing a new adapter, not modifying the engine. If a future change requires touching
`engine.py`/`content_metrics.py`/`topics.py` to support a new platform, that is itself
a signal the platform-agnostic boundary was drawn in the wrong place and needs a new
decision recorded here.

### ADR-008 — AI explains deterministic calculations; it never invents them
**Context:** Multiple sprints explicitly deferred AI ("do not implement AI yet") while
building the deterministic layer AI will eventually sit on top of.
**Decision:** A future AI layer consumes the already-computed `Recommendation`
objects (headline, explanation, confidence, supporting metrics/videos) to produce
better narration. It never computes its own numbers, never asserts a trend the
deterministic engine didn't detect, and never overrides a confidence gate.
**Consequences:** See [AI_ENGINE.md](./AI_ENGINE.md). If AI-generated text and the
deterministic numbers ever disagree, the deterministic numbers are correct by
definition and the AI output is a bug.

### ADR-009 — No automatic sync until a scheduler is explicitly built and enabled
**Context:** A full scheduler design was planned (Sprint 3) but not implemented, to
avoid silently introducing new infrastructure (a new Docker service, a new failure
mode) without explicit approval.
**Decision:** Sync remains manual-only until a scheduler ships. When it does, it must
default to disabled (`YOUTUBE_SYNC_ENABLED=false`) and require explicit opt-in.
**Consequences:** Sprint 4.1's sync-visibility work (durations, counts, errors on
every manual run) stands on its own regardless of when/whether the scheduler is built.

### ADR-010 — Workspaces are the future architecture for multiple brands
**Context:** RCC is single-tenant today (one set of connected accounts, no
user-scoped isolation) but is intended to support multiple real brands/clients
through the same instance — named explicitly: **Łukasz Oleś** (the current connected
channel) and **BTLA**, plus future clients.
**Decision:** The future `Workspace` entity scopes `PlatformAccount` (and everything
downstream — channels, videos, snapshots, intelligence) per brand/client, not as an
abstract multi-tenancy feature bolted on later. Expect a brand/workspace switcher in
the UI when this ships, not just backend data isolation.
**Consequences:** Any interim single-tenant shortcuts (e.g. "most recently synced
channel" queries) should be written so they're easy to re-scope by workspace later,
not deeply hardcoded to "there is exactly one channel."

### ADR-011 — Prefer extending existing endpoints over creating new ones
**Context:** Recurring choice point almost every sprint when a page needed more data.
**Decision:** Default to adding fields to an existing endpoint/schema. Only create a
new endpoint when the capability is genuinely a different resource (e.g.
`/analytics/intelligence` was a justified new endpoint — a full recommendation report
is not a natural extension of any single existing resource).
**Consequences:** `/videos` and `/videos/{id}` have grown structured metadata fields
(Sprint 5) rather than spawning parallel "enriched" endpoints.

### ADR-012 — Dark theme only; no parallel visual language
**Context:** Established in the earliest sprint (`#070a11` background, `#5cf0ac`
accent) and never revisited.
**Decision:** All new UI reuses RCC's existing dark palette and component patterns
(`StatCard`, `RankedVideoList`, badge conventions). No light mode, no second design
system, no per-page visual reinvention.
**Consequences:** "Do not redesign" in a sprint brief means exactly this — extend the
existing visual language, don't introduce a new one alongside it.

### ADR-013 — History charts are anchored to content age, never to sync timestamps
**Context:** Sprint 5/6 both independently required this: raw synchronization
timestamps make an irregular sync cadence (manual clicks, uneven intervals) look like
the shape of the data itself, which is misleading and can show dozens of
near-identical points.
**Decision:** Every history chart (`content_metrics.bucket_history`, and the
channel-history equivalent) buckets by elapsed time since a content-relevant anchor
(a video's publish date; a channel's first tracked snapshot) — daily under 30 days,
weekly 30–180 days, monthly beyond that — and shows an explanatory empty state
instead of a chart when fewer than 2 periods exist.
**Consequences:** This is a generic function in the platform-agnostic
`content_metrics.py`, not YouTube-specific — any future platform's video history
buckets the same way for free.

### ADR-014 — Snapshot dedup is time-window based, not value-based
**Context:** Sprint 6 needed a deterministic answer to "what counts as an accidental
duplicate snapshot" (Part 3).
**Decision:** A snapshot is a duplicate only if the same video/channel already has
one captured within the last 5 minutes (`MIN_SNAPSHOT_INTERVAL_MINUTES`) — never
based on whether the values are unchanged. Two legitimate periodic syncs 6 hours
apart with identical view counts are NOT deduplicated; that "no growth" data point is
real signal (feeds `Trend.DECLINING`), not noise.
**Consequences:** Any future sync-triggering path (manual button, scheduler, a
webhook) shares this one guard in `youtube_sync.py` — don't add a second,
value-based dedup check elsewhere; it would silently erase legitimate zero-growth
history.

### ADR-015 — The automatic sync scheduler runs in-process, not as a separate service
**Context:** Sprint 3's original plan and ADR-009 both anticipated a scheduler; Sprint
6 had to decide its actual shape.
**Decision:** `app/services/youtube_scheduler.py` is a single asyncio background task
started from the existing backend container's FastAPI `lifespan`, not a new Docker
service, not Celery/APScheduler. Still disabled by default (`YOUTUBE_SYNC_ENABLED`)
per ADR-009.
**Consequences:** Simpler to reason about and operate for a single-tenant tool with
one sync target. Revisit this decision (a real worker service, e.g. once Redis is
used for more than incidental config) only if RCC needs to run sync jobs across
multiple processes/replicas — not before.

### ADR-016 — `GET /status` is the single source of truth for synchronization state
**Context:** Release 0.6.1 bugfix. Home, the YouTube Dashboard, and Video Detail each
independently read a `last_synced_at` computed by `get_summary()`, while the YouTube
integration panel read a separately-computed `last_synced_at` from `GET /status`.
Both ultimately queried `channel.synced_at`, so they could never differ in the
database — but they were fetched at different times (one server-rendered at page
load, one client-fetched on mount) with no shared cache-invalidation, so a sync
triggered from the panel updated its own client state immediately while the
server-rendered value elsewhere on the same page stayed frozen until a full reload.
**Decision:** `SummaryRead`/`get_summary()` no longer expose `last_synced_at` at all.
Every page that displays synchronization time/status renders the shared
`<SyncStatusLine>` component fed by `GET /status` — never a separately-fetched or
independently-computed timestamp. `youtube_analytics.get_channel()` is also now the
one function every backend code path uses to look up "the connected YouTube
channel" (previously `/status` and `get_summary()` used two independently-written
queries that happened to agree only because RCC has exactly one channel today).
**Consequences:** After a sync, `YoutubePanel` calls `router.refresh()` so the
current page's server components re-fetch immediately; `next.config.js` sets
`experimental.staleTimes.dynamic = 0` so navigating to any other page always hits
the server for fresh data instead of a cached RSC payload. Any future page that
needs to show sync state must reuse `<SyncStatusLine>` + `GET /status` — adding a
new independent `last_synced_at` read anywhere is the exact regression this ADR
exists to prevent.

### ADR-017 — `youtube.force-ssl` is the OAuth scope for comment read/write
**Context:** Release 0.7.0's Community Inbox needs to read and post YouTube
comments. The existing scopes (`youtube.readonly`, `yt-analytics.readonly`) permit
neither.
**Decision:** Request `https://www.googleapis.com/auth/youtube.force-ssl` (replacing
`youtube.readonly`, which it is a strict superset of) instead of inventing a
narrower custom scope combination. This is the least-privilege *official* scope
that permits posting/editing/deleting comments — there is no separate
"comments-only" scope YouTube offers.
**Consequences:** Every account connected before this release must reconnect once
to grant the new scope (the existing OAuth callback already upserts by channel ID,
so this never loses analytics data or sync history — see `api/youtube.py::callback`).
`YoutubeStatus.comments_scope_granted`/`comments_reconnect_required` and
`has_comments_scope()` are the one place this is checked; never re-implement the
scope string check inline elsewhere.

### ADR-018 — Comment sync reuses the video-sync engine's patterns exactly
**Context:** Release 0.7.0 needed an idempotent, quota-conscious, fault-isolated
comment sync. Sprint 6 had already solved this exact set of problems for video
metrics.
**Decision:** `youtube_comment_sync.py` mirrors `youtube_sync.py` deliberately: an
overlap guard + stale-run reclaim (`SyncRun.platform="youtube_comments"`, same
`SyncRun` table as video sync — one audit mechanism, discriminated by `platform`,
not a parallel table), per-video fault isolation via SQL savepoints, and upsert-only
persistence (a thread/comment is never deleted just because a later sync omits it —
matching `YoutubeMetricSnapshot`'s "never delete history" principle). The
quota-conscious strategy (recent videos every run, older videos every 4th run, or
an explicit manual full refresh) is the one genuinely new piece, since video-metric
sync doesn't have a "how far back to look" dimension the way comment threads do.
**Consequences:** A future platform's comment/message sync (Facebook comments,
Instagram DMs) should follow this same shape rather than reinventing dedup/overlap
handling from scratch.

### ADR-019 — Conversation state is derived from the LAST message in the full thread
**Context:** Release 0.7.1 bugfix. The original 0.7.0 "answered" logic was `any
reply exists from the channel` — which stayed `True` forever even after a viewer
replied again following the channel's answer, silently hiding conversations that
still needed attention. Live verification against the real connected channel also
found a second bug from the same root cause: a channel's own pinned top-level
comment (a common creator practice — e.g. linking the full video under a Short)
has zero replies, so it was flagged "New / needs reply" even though the channel
already has the only word in that thread.
**Decision:** `comment_intelligence.determine_conversation_state` is the ONE
function every consumer calls (Inbox, Home, Video Detail, priority scoring,
filters/summaries) — never a locally re-derived binary answered/unanswered flag.
Priority order: **Closed** (moderated) → **New** (the channel has never spoken in
this thread, counting BOTH its own replies AND a self-authored top-level comment)
→ **Resolved** (the channel's message is the most recent in the full thread) →
**Waiting** (the channel spoke before, but the viewer replied again since).
Evaluation always considers the complete thread (top-level comment + every
reply), never the top-level comment in isolation.
**Consequences:** `comment_priority_score` takes the resulting `state` directly
(never a raw boolean) and always scores Resolved/Closed as `0` — "never
prioritize an already-resolved conversation" is enforced structurally, not by
convention. Any future comment-adjacent feature (e.g. a Facebook Messenger-style
inbox) should reuse this exact state machine rather than inventing a new
answered/unanswered concept.
