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
