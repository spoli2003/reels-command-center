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

### ADR-020 — Release 0.8.0 activates the unified content engine instead of building parallel platform stacks
**Context:** Release 0.8.0 adds Facebook and Instagram and explicitly forbids
`youtubeService`/`facebookService`/`instagramService`-style duplication. RCC
already has two candidate homes for new platforms: (a) copy the YouTube-specific
pattern (`FacebookVideo`, `FacebookMetricSnapshot`, ... — what ADR-003
deliberately avoided) or (b) finally populate `ContentVideo`/`Publication`/
`MetricSnapshot`, the cross-platform engine built in Sprint 1 and left
intentionally unused until "a second platform integration exists" (ADR-003).
That moment is now.
**Decision:**
1. Facebook and Instagram sync directly into the unified engine
   (`ContentVideo`/`Publication`/`MetricSnapshot`) via a small `PlatformAdapter`
   protocol (`app/services/platforms/base.py`) — one generic sync service
   (`content_sync.py`), not per-platform copies. `MetricSnapshot` already has
   `reach`/`impressions`/`shares`/`saves`/`watch_time_seconds`/
   `followers_gained` — fields YouTube's Data API can't provide but Facebook/
   Instagram Insights can, so the unified schema needed no changes.
2. Comments get the same treatment: new generic `ContentCommentThread`/
   `ContentComment` tables (FK'd to `Publication`, not `YoutubeVideo`), a generic
   `content_comment_sync.py`/`content_comments_query.py`/`content_comment_actions.py`
   trio mirroring the YouTube comment services' shape exactly, and reusing
   `comment_intelligence.py` completely unchanged — it was already
   platform-agnostic (pure functions over booleans/timestamps).
3. **YouTube's existing dedicated pipeline is not touched or migrated.** It is
   mature, tested across 8 prior releases, and live-verified against a real
   channel — rewriting it onto the unified engine this release would be pure
   regression risk for zero user-facing benefit. Instead, YouTube sync gets one
   small additive step: after each sync, upsert corresponding
   `ContentVideo`/`Publication`/`MetricSnapshot` rows too (a "dual-write
   bridge," `youtube_unified_bridge.py`). This makes YouTube data ALSO visible
   through the new generic multi-platform surfaces without changing a single
   existing YouTube endpoint, schema, or test.
4. A new generic API namespace (`/api/platforms/{platform}/...`) is the ONE
   contract the frontend's generic Dashboard/Videos/Compare/Intelligence/
   Community pages call, regardless of platform. For `platform=youtube`, these
   generic endpoints are thin wrappers translating the existing YouTube-specific
   service responses into the generic shape — reuse, not reimplementation. For
   `facebook`/`instagram`, they're real implementations against the unified
   engine.
**Consequences:** RCC now has two YouTube surfaces on purpose: the original
`/youtube/*` deep pages (full Sprint 5/6/0.7.x feature depth: sortable tables,
history bucketing, quota-aware scheduler, dedicated comment engine) stay exactly
as they are, and a new `/platforms/youtube` generic surface (baseline dashboard/
videos/compare/intelligence/community, shared with Facebook/Instagram) is
additive. Facebook and Instagram start at this shared baseline, not at
YouTube's full depth — closing that gap is future work (see TODO.md), not a
regression, since YouTube never had this generic surface before. Any future
platform (TikTok) is a new `PlatformAdapter` implementation only — no new
tables, no new sync service, no new API router.

### ADR-021 — Meta OAuth uses one App ID/Secret for both Facebook and Instagram
**Context:** Facebook Pages and Instagram professional accounts are both
authorized through the same Meta Graph API OAuth flow — an Instagram Business/
Creator account is only reachable via its linked Facebook Page, there is no
separate "Instagram-only" OAuth app.
**Decision:** One Meta OAuth app (`META_APP_ID`/`META_APP_SECRET`/
`META_REDIRECT_URI` env vars, mirroring the existing `GOOGLE_CLIENT_SECRETS_FILE`
pattern) drives `/api/platforms/meta/connect`. After consent, RCC lists the
user's Facebook Pages (`GET /me/accounts`); for each Page it also resolves any
linked Instagram professional account
(`GET /{page-id}?fields=instagram_business_account`). Connecting a Facebook Page
and connecting its Instagram account are two distinct `PlatformAccount` rows
(`platform="facebook"` / `platform="instagram"`) sharing the underlying Page
access token, following the existing `PlatformAccount` shape exactly (no new
account model).
**Consequences:** The user must create a Meta Developer App and provide its App
ID/Secret before Facebook/Instagram can be connected — RCC cannot create this
app on their behalf (same bootstrap step YouTube required with
`google_client_secret.json`). Meta's App Review process may gate some
permissions for accounts outside the developer's own — documented honestly in
KNOWN_ISSUES.md rather than worked around.

### ADR-022 — Optional Facebook Login for Business Configuration support (`META_LOGIN_CONFIG_ID`)
**Context:** ADR-021 assumed the classic Facebook Login product (App Dashboard
→ Facebook Login → Settings → scope-based Valid OAuth Redirect URIs). In
practice, some Meta app types (Business-type apps in particular) only expose
"Facebook Login for Business" in the console, which replaces that screen
entirely with named **Configurations** — each Configuration pre-defines its own
permission set server-side and is referenced by a Configuration ID at authorize
time; the classic `scope` parameter has no effect once a Configuration is used,
and sending it alongside `config_id` is not part of Meta's documented
Configuration-based Login flow.
**Decision:** `build_authorization_url()` (`app/integrations/meta/oauth.py`)
branches on a new optional setting, `META_LOGIN_CONFIG_ID`: when set, the
authorize URL sends `config_id` and omits `scope` entirely (the Configuration
owns the permission set — see the exact 8 permissions in
`app/integrations/meta/oauth.py::SCOPES`, which must be assigned to the
Configuration in the Meta dashboard instead of requested at authorize time).
When unset (the default), the classic `SCOPES`-based flow from ADR-021 is used
unchanged. Nothing downstream of the authorize dialog changes either way — code
exchange (`exchange_code_for_token`), long-lived token exchange
(`exchange_for_long_lived_token`), Page listing (`list_pages`), and Instagram
resolution (`get_linked_instagram_account`) are all identical regardless of
which path built the initial redirect.
**Consequences:** Setting up Meta credentials now has two possible dashboard
paths depending on the app type Meta assigned — documented step-by-step for
both in this session's guidance (not yet folded into a standing doc; a future
pass could add a `docs/META_SETUP.md` walkthrough once verified against a real
Configuration). `GraphClient`'s Graph API version was also decoupled from a
hardcoded module constant in the same pass — it now takes `graph_api_version`
per instance, sourced from `settings.meta_graph_api_version` in
`app/api/platforms.py::_build_adapter`, matching what `oauth.py` already did
(a real inconsistency found during Meta credential setup, not a regression
introduced here — see `KNOWN_ISSUES.md`).

### ADR-023 — Meta connect always shows an explicit Page picker; never auto-connects the first Page (Release 0.8.1)
**Context:** ADR-021's original `meta_callback()` unconditionally picked
`pages[0]` from `GET /me/accounts` and connected it immediately — documented at
the time as a "first-Page-only" scope cut. In practice this is unsafe for
anyone managing more than one Facebook Page: RCC would silently connect
whichever Page happens to sort first, with no way to choose, and no visibility
into which Page (or its linked Instagram account) was actually picked before
it's a done deal.
**Decision:** `meta_callback()` no longer writes a `PlatformAccount` at all. It
fetches every Page the Meta account manages, eagerly resolves each Page's
linked Instagram account (`get_linked_instagram_account`) so the picker can
show it without a second round-trip, and stores the candidate list server-side
keyed by an opaque `selection_id` (`app/services/meta_pending_selection.py`,
in-memory, 10-minute TTL). It then redirects the browser to a new frontend
screen, `/platforms/meta/select-page?selection=<id>`, which lists every Page
(picture, name, category, follower count, linked Instagram username if any)
and requires an explicit click before anything is connected. `POST
/api/platforms/meta/select-page` is the only place a `PlatformAccount` row gets
written, using the chosen Page's access token; the selection is single-use
(`consume_selection`) on success, but deliberately left alive on a recoverable
error (picking a Page with no linked Instagram while connecting Instagram) so
the user can try a different Page from the same screen without restarting
OAuth.

The pending-selection store is deliberately **not** the session cookie used for
the `/meta/connect` → `/meta/callback` CSRF `state` check: the picker is
rendered by the frontend (a different port than the backend that owns that
session cookie), and a cross-origin `fetch()` reliably carrying a cookie back
depends on `FRONTEND_URL`/`NEXT_PUBLIC_API_URL`/`META_REDIRECT_URI` all using
the exact same hostname (`localhost` vs `127.0.0.1` alone breaks it — see
ADR-022's Configuration work for the same class of hostname pitfall). An opaque
ID traveling in the redirect URL sidesteps that fragility entirely and works
regardless of hostname choices.
**Consequences:** In-memory + single-process + TTL-based, not a database table
— acceptable because the data is genuinely ephemeral (nothing is real until a
Page is chosen) and RCC runs one uvicorn process with no `--workers`; a backend
restart mid-pick just means reconnecting, never a half-written account. Not yet
verified against a real Meta account with multiple Pages — see
`KNOWN_ISSUES.md`.

### ADR-024 — Real Meta OAuth debugging: hostname-scoped session cookie, a credential leak, and `business_management`
**Context:** The first real connection attempt against a live Meta account surfaced three distinct, unrelated bugs in sequence, each only reachable once real credentials existed (nothing in 0.8.0/0.8.1's fake-Graph-API test suite could have caught any of them — see KNOWN_ISSUES.md's standing caveat about that gap).

**1. "Nieprawidłowy stan OAuth" on every attempt.** Root cause, confirmed via a temporary runtime diagnostic (`_log_oauth_diagnostics` in `app/api/platforms.py`, kept permanently — cheap, and this class of bug can recur) and reproduced deterministically with `curl`: `NEXT_PUBLIC_API_URL` (docker-compose.yml) was `http://127.0.0.1:8000` while `META_REDIRECT_URI` was `http://localhost:8000/...`. The session cookie carrying the CSRF `state` is host-only (no `Domain=` set — Starlette's `SessionMiddleware` default); `127.0.0.1` and `localhost` are different hosts for cookie storage even though both resolve to loopback. The cookie set during `/meta/connect` never reached `/meta/callback`. **Fix:** every URL a browser touches during this flow — `NEXT_PUBLIC_API_URL`, `FRONTEND_URL`, `META_REDIRECT_URI` — must share one hostname. Standardized on `localhost` (documented in `.env.example` and inline in `docker-compose.yml`).

**2. Credential leak in logs.** Reproducing bug 1 with a deliberately-fake authorization code surfaced a second, independent bug: `oauth.py`'s token-exchange calls and `client.py`'s `GraphClient` both send secrets (`client_secret`, access tokens) as query parameters (Meta requires this), and on failure, `httpx.HTTPStatusError`'s message embeds the full request URL verbatim. The App Secret appeared in cleartext in `docker compose logs`. **Fix:** `MetaOAuthError` (oauth.py) and a hardened `GraphAPIError` (client.py) — both raised with `from None` and a fixed, credential-free message (`f"...failed with HTTP {status_code}"`), never `str(exc)` or the chained original exception. Regression-tested (`test_meta_oauth.py`, `test_meta_graph_client.py`) by asserting the literal secret string never appears in the raised exception. **The exposed App Secret was rotated** — this is an operational action taken outside the codebase, not a code change.

**3. `/me/accounts` returns `{"data": []}` despite confirmed Page ownership.** Runtime diagnostics (`GET /me/permissions`, `GET /debug_token`) proved: the token is a genuine `USER`-type token (not a Page/App token — `get_me()` resolves a real personal name, which a Page token could not); `pages_show_list` is granted; but it is the *only* one of RCC's 9 requested permissions actually granted — the Facebook Login for Business Configuration was not attaching the rest. Cross-referenced against Meta's developer community (multiple independent reports of the identical symptom: `pages_show_list` granted, Page confirmed Business-Portfolio-owned, `/me/accounts` empty) converging on one specific missing permission: **`business_management`**. Meta's documented behavior is that a Page living inside a Business Portfolio is not returned by `/me/accounts` on `pages_show_list` alone, regardless of the user's actual admin level on that Page. **Fix:** added `business_management` to `SCOPES` (oauth.py) — requires the corresponding dashboard action of adding it to the Configuration's Permissions step (same App Dashboard flow as the other 8 permissions, not a Business Suite/Business Manager setting). `/me/accounts` remains the correct endpoint; switching to Business Manager's `owned_pages`/`client_pages` endpoints was considered and rejected as unnecessary — multiple corroborating reports confirm `/me/accounts` starts returning Pages correctly once `business_management` is granted, and introducing a second Page-listing code path for no functional gain would be pure added complexity.

**Consequences:** The empty-Pages error message (`meta_callback`) no longer claims the account manages no Pages — it inspects `GET /me/permissions` and returns one of two specific, actionable messages (missing `pages_show_list` vs. granted-but-nothing-shared), since the original message was proven actively misleading in exactly this scenario. After the real Facebook flow was verified, the diagnostics were reduced to compact credential-free facts (token type/scopes/validity, Page count/tasks and whether Instagram is linked); raw Page/profile payloads are no longer logged. `_log_oauth_diagnostics` remains as cheap defense-in-depth for the hostname-mismatch class of bug specifically.

### ADR-025 — Instagram uses the linked-Page professional-account flow and one Meta sync orchestrator (Release 0.8.3)
**Context:** Instagram API with Facebook Login exposes a Business or Creator
professional account through its linked Facebook Page. The 0.8.0 adapter existed,
but the live Configuration granted no Instagram permissions, Page selection did
not start a sync, media/comments were only single-page reads, and one unsupported
insight metric could erase all otherwise-valid insight data.

**Decision:** RCC discovers `instagram_business_account` inline on
the selected Page after a deliberately minimal `GET /me/accounts` Page-list
request. The real Meta callback proved that expanding optional Instagram
profile fields inside `/me/accounts` can make Meta reject the entire Page list
with HTTP 400. RCC therefore resolves only `instagram_business_account` on the
Page first and enriches the returned Instagram id in a separate, non-critical
request; a 400/403 during display-only enrichment keeps the id and never blocks
`PlatformAccount` creation.
Connection requires the complete least-privilege set used by the shipped feature:
`pages_show_list`, `business_management`, `pages_read_engagement`,
`instagram_basic`, `instagram_manage_comments`, and
`read_insights`. The active Facebook Login for Business Configuration exposes
`read_insights`; RCC therefore validates the capability Meta actually grants
instead of requiring the unavailable `instagram_manage_insights` name. Initial,
manual and scheduled Facebook/Instagram
sync all call `sync_meta_account()`; the opt-in in-process Meta scheduler mirrors
ADR-015 and never introduces a second implementation. Media, comments and replies
follow cursor pagination. Insights are fetched independently per metric, and
unsupported metrics are unavailable rather than inferred (especially: reach is
never presented as views).

**Consequences:** Editing a Facebook Login for Business Configuration requires
removing the old Business Integration grant and reconnecting before the new scopes
appear on the token. A successfully-created account is kept connected if its first
sync fails, with an explicit warning and a retry button; OAuth is not needlessly
repeated for a transient data failure. Meta automatic sync stays disabled by
default. Uvicorn raw access logs are disabled because OAuth callback query strings
contain one-time credentials; compact credential-free diagnostics remain.
