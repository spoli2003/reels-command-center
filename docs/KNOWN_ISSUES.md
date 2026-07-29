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

## Community Inbox (Release 0.7.0)

- **The currently connected YouTube account must be reconnected before comments
  work with real data.** It was authorized before this release under the old
  `youtube.readonly` scope, which doesn't permit reading or posting comments. This
  is expected, not a bug — `GET /status` correctly reports
  `comments_scope_granted: false` / `comments_reconnect_required: true`, and the
  YouTube panel shows a reconnect prompt. Reconnecting is additive/safe (see
  ADR-017) and is the one action item tracked in [TODO.md](./TODO.md) that this
  session could not perform itself (it requires an interactive Google consent
  screen).
- **No live comment sync or real reply was verified this release**, as a direct
  consequence of the above — the backend gate (`_require_comments_scope`) was
  confirmed to correctly reject the manual sync/reply endpoints with a clear 403
  against the real (not-yet-reconnected) account, and all functionality was
  verified via 15 dedicated mocked-API tests (`test_youtube_comments.py`) plus a
  clean frontend production build. Live verification (a real sync, spot-checking
  real threads, and — only with explicit approval — publishing one real test
  reply) is still owed once the account is reconnected.
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
- **No automated visual/responsive browser testing for the Community Inbox either**
  — same caveat as Sprint 5/6 below. Layouts (comment cards, reply composer, quick-
  reply manager) follow the existing 1100px/760px breakpoints but haven't been
  visually confirmed in an actual browser, especially at mobile width where a
  comment card's header/badges/reply composer stack could get cramped.

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

- **The automatic sync scheduler (Sprint 6 / Part 5) is disabled by default and was
  not enabled/observed running for a full interval in this session** (per ADR-009,
  enabling it is a deliberate operator choice, not something to flip on during
  development). Its individual pieces (overlap guard, stale-run reclaim, dedup) were
  verified directly against the manual `/sync` endpoint with real data; the
  `asyncio` loop itself was verified only by static review and a successful FastAPI
  startup/shutdown cycle, not a live multi-hour run.
