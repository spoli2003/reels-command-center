# Known Issues

Honest, current gaps and limitations — not a bug tracker for every papercut, but a
place to record anything a future session (AI or human) should know about before
assuming a screen or number is fully correct. See [DECISIONS.md](./DECISIONS.md) for
the architectural reasoning behind related tradeoffs.

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
  [TODO.md](./TODO.md) to make the distinction more visually unmissable.

## Verification

- **No browser-based visual/responsive testing was performed for Sprint 5/6.** This
  session had no browser automation tool available. Verification was: full backend
  test suite (58 tests), a clean frontend production build (type-checked, all 8
  routes prerendered), and HTTP-level checks (status codes + presence of expected
  markup) against the real connected YouTube channel. The responsive CSS added for
  the new components (sortable headers, quick-filter row, video timeline, technical
  metadata grid) follows the existing breakpoint conventions (1100px/760px) but has
  not been visually confirmed in an actual browser at tablet/mobile widths.
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
