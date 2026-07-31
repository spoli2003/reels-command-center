# Known Issues

Honest, current gaps and limitations — not a bug tracker for every papercut, but a
place to record anything a future session (AI or human) should know about before
assuming a screen or number is fully correct. See [DECISIONS.md](./DECISIONS.md) for
the architectural reasoning behind related tradeoffs.

## Resolved

- ~~Home/Dashboard/Video Detail could show a different "last synchronization"
  timestamp than the YouTube panel, and other pages didn't refresh after a manual
  sync without a full reload.~~ Fixed in **Release 0.6.1** — see ADR-016 and the
  changelog entry. `GET /status` is now the only source read for sync time/status
  anywhere in the app, and the Router Cache no longer serves stale RSC payloads for
  dynamic routes.
- ~~A conversation stayed marked "answered" forever after the channel's first
  reply, even if the viewer replied again since — and a channel's own pinned
  top-level comment was wrongly flagged "New / needs reply."~~ Fixed in
  **Release 0.7.1** — see ADR-019. Conversation state is now derived from the
  last message in the complete thread (counting the top-level comment's own
  authorship too), computed by one shared function everywhere.
- ~~The connected account needed reconnecting to grant the `youtube.force-ssl`
  scope before Community Inbox worked with real data.~~ Done by the operator —
  real comment sync and real replies are live on the connected channel as of
  Release 0.7.1's verification pass.

## Facebook & Instagram (Release 0.8.0–0.8.3)

- **First real-account connection attempt surfaced three bugs, fixed — see
  ADR-024:** (1) a hostname mismatch between `NEXT_PUBLIC_API_URL`/
  `FRONTEND_URL`/`META_REDIRECT_URI` broke the OAuth CSRF `state` check on
  every attempt; (2) a failed token exchange leaked the App Secret into logs
  (the exposed secret was rotated); (3) `/me/accounts` returned an empty Page
  list for a confirmed Page admin because the Facebook Login for Business
  Configuration was only actually granting `pages_show_list`, and — per
  multiple corroborating Meta developer-community reports — a
  Business-Portfolio-owned Page additionally requires `business_management`,
  now added to `SCOPES`.
- **The real Facebook flow is verified:** `business_management` and
  `pages_show_list` are granted, `/me/accounts` returns the Page, Page selection
  succeeds and Facebook synchronization is live. Compact token/Page diagnostics
  remain intentionally, without tokens, raw profile payloads or callback query
  strings.
- **A real Instagram callback exposed an over-broad Page discovery request,
  now fixed.** Expanding `instagram_business_account` plus optional profile
  fields inline in `/me/accounts` made Meta reject the complete Page list with
  HTTP 400. Page discovery is now minimal; the Instagram relationship and its
  display-only details are fetched separately, and optional enrichment cannot
  hide a valid Facebook Page or crash the callback.
- **The live Instagram connection still needs an operator-side permission
  grant.** Add `instagram_basic`, `instagram_manage_comments` and
  `read_insights` to the active Facebook Login for Business
  Configuration (alongside `pages_show_list`, `business_management` and
  `pages_read_engagement`), remove the old RCC grant from Facebook Business
  Integrations, then reconnect. Until Meta actually returns these scopes on
  `/debug_token`, RCC correctly refuses to claim Instagram is connected.
- **Instagram 0.8.3 is regression-tested but not yet verified against the real
  account's media.** The live blocker is the Configuration grant above, not an
  unresolved code path. After reconnect, verify the automatic first sync,
  manual sync, media/insights and Community against real data before treating
  Instagram as production-verified.
- **The Page Selection screen (Release 0.8.1, ADR-023) has not been verified
  against a real Meta account managing multiple Facebook Pages.** The flow
  (fetch every Page → hold server-side → user picks → connect) is covered by
  end-to-end tests against a fake Graph API, including the multi-Page case,
  but nobody has yet clicked through the real screen with a real multi-Page
  account. Verify this before relying on it if you manage more than one Page.
- ~~`META_LOGIN_CONFIG_ID` had only fake-client coverage.~~ Verified against the
  real Facebook Login for Business Configuration during the Facebook flow.
- **Two real bugs were found and fixed during Meta credential setup, before
  any real credentials were entered:** (1) the default `META_REDIRECT_URI`
  used `127.0.0.1`, which Meta's HTTPS-enforcement exemption for local
  redirect URIs generally does not cover (only the literal `localhost`
  hostname is exempted) — changed to `http://localhost:8000/api/platforms/meta/callback`.
  (2) `GraphClient` (`app/integrations/meta/client.py`) hardcoded
  `GRAPH_API_VERSION = "v19.0"` as a module-level constant, completely
  ignoring `settings.meta_graph_api_version` — meaning `oauth.py`'s dialog/
  token-exchange calls honored a configured API version while every actual
  Graph API data/comment call in `client.py` silently didn't. Fixed:
  `GraphClient` now takes `graph_api_version` per instance, sourced from
  settings in `app/api/platforms.py::_build_adapter`.
- **The pending Page Selection store is in-memory and single-process**
  (`app/services/meta_pending_selection.py`, 10-minute TTL) — a deliberate
  choice for genuinely ephemeral pre-connection data (see ADR-023), not
  suitable if RCC is ever run with multiple backend workers/processes; a
  backend restart mid-pick just means reconnecting, no partial account is
  ever written.
- **The Meta scheduler is opt-in and has not yet been left running against the
  real Instagram account.** It reuses the manual sync path and is disabled by
  default. Enable only after the real reconnect succeeds by setting
  `META_SYNC_ENABLED=true`; its minimum interval is one minute and the local
  default/recommendation is six hours.
- **Facebook/Instagram start at the generic `/platforms/*` surface's baseline
  depth**, not YouTube's full Sprint 5/6/0.7.x depth: no channel-wide
  subscriber/view history chart (Meta's Insights API doesn't expose an
  equivalent to YouTube's channel snapshot history the same way), no
  data-quality audit, no quota-aware incremental sync. This is additive scope,
  not a regression — these platforms never had that depth before.

## Community Inbox

- **"Double-submit protection" for replies is a UI-only guard** (the composer
  disables itself while a request is in flight), not a backend idempotency key.
  There's no natural request-level dedup for arbitrary free-text replies against
  the real YouTube API — a genuine duplicate would require the user to submit the
  exact same text twice in two separate, deliberate clicks after the first one
  already completed, which the UI already prevents by disabling the button mid-
  flight.
- **Quick-reply templates are scoped by `PlatformAccount`, not by a `Workspace`**,
  because Workspace doesn't exist yet (see ADR-010). This is a deliberate,
  documented interim scope — the model's shape doesn't need to change when
  Workspace ships, only the ownership column.
- **The YouTube Data API does not support liking comments at all** (Release
  0.7.1 / Part 3) — RCC displays like counts, supports sorting/highlighting by
  them, and reads `viewerRating` (whether the channel owner already liked a
  comment, read-only) where the API provides it, but there is deliberately no
  Like button anywhere: it would either be fake or require scraping/browser
  automation, both explicitly disallowed.
- **No automated visual/responsive browser testing for the Community Inbox**
  — same caveat as Sprint 5/6 below. Layouts (comment cards, reply composer,
  quick-reply manager, conversation-state/priority badges) follow the existing
  1100px/760px breakpoints but haven't been visually confirmed in an actual
  browser, especially at mobile width where a comment card's header/badges/reply
  composer stack could get cramped.
- **Home now surfaces five community-related facts** (awaiting reply, new
  questions, resolved, most-discussed video, recently-active discussions).
  Individually each is a one-line summary with a single link out to the Inbox,
  consistent with "Home is not a full comment-management screen" — but worth a
  future glance if more community facts get added here, to keep it that way.

## Data

- **YouTube's own view counts occasionally decrease between syncs.** The data-quality
  audit (`GET /api/integrations/youtube/data-quality`, Sprint 6 / Part 13) found a
  real instance on the connected channel: a video's views dropped by 3 between two
  snapshots. This is not an RCC bug — YouTube periodically removes spam/bot views
  after the fact. RCC reports this honestly (via the audit endpoint and the existing
  "possible data correction" wording on the video detail page's snapshot-delta
  insight) rather than hiding or "correcting" it.
- **Two related but intentionally different performance scores/labels can appear on
  the same page.** The backend's `/videos` response includes a channel-wide
  `performance_score`/`performance_label` (Sprint 5 / Part 8). The frontend also
  computes its own filter-scoped composite score for ranked lists like "Najlepsze
  filmy" on the dashboard. Both are correct for what they measure (see ADR-005 —
  every score states what it's relative to), but a video can show two different
  numbers in two places on the same screen. Tracked as a follow-up in
  [TODO.md](./TODO.md) to make the distinction more visually unmissable. This is
  architecturally different from the 0.6.1 sync-timestamp bug: both scores are
  *always* fresh and *deliberately* scoped differently, they just aren't visually
  distinguished enough yet.

## Verification

- **No browser-based visual/responsive testing was performed for Sprint 5/6/0.6.1.**
  This session had no browser automation tool available. Verification was: full
  backend test suite (59 tests), a clean frontend production build (type-checked,
  all 8 routes prerendered), and HTTP-level checks (status codes + presence of
  expected markup, including exact timestamp comparison across pages before/after
  live syncs) against the real connected YouTube channel. The responsive CSS added
  for the new components (sortable headers, quick-filter row, video timeline,
  technical metadata grid) follows the existing breakpoint conventions
  (1100px/760px) but has not been visually confirmed in an actual browser at
  tablet/mobile widths.
- **The 0.6.1 fix for the Next.js client-side Router Cache
  (`experimental.staleTimes.dynamic = 0`) was verified by code/config review and by
  confirming every page's server-rendered HTML is correct per-request (via curl),
  not by an actual browser navigation test** (e.g. clicking "Synchronize now" then
  clicking a `<Link>` to another already-visited page within the old 30s cache
  window). The server-side fix (one shared data source, `router.refresh()`) is
  independently sufficient and verified; the Router Cache change is defense in
  depth for the client-side navigation case specifically, and is worth a manual
  browser check when one is available.
- **The channel-wide subscriber-growth chart has not been visually verified with real
  multi-period data.** RCC has only been tracking channel-level snapshots for a
  short time on the connected instance, so `GET /channel/history` currently returns
  `insufficient: true` and the dashboard correctly shows the explanatory empty state
  instead of a chart. The chart itself should be spot-checked again once enough
  history accumulates.

## Infrastructure

- **`Synchronizuj wszystko` is synchronous in Release 0.8.4b.** The request
  waits for each connected provider in sequence and returns one aggregate result.
  Provider failures are isolated and reported honestly, but a future multi-user
  deployment should move this orchestration to a durable job queue before adding
  long-running providers such as TikTok.

- **The automatic sync scheduler (Sprint 6 / Part 5) is disabled by default and was
  not enabled/observed running for a full interval in this session** (per ADR-009,
  enabling it is a deliberate operator choice, not something to flip on during
  development). Its individual pieces (overlap guard, stale-run reclaim, dedup) were
  verified directly against the manual `/sync` endpoint with real data; the
  `asyncio` loop itself was verified only by static review and a successful FastAPI
  startup/shutdown cycle, not a live multi-hour run.
