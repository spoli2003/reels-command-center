# TODO

Grouped by timeframe, then by category. This is the working roadmap — see
[ROADMAP.md](./ROADMAP.md) for the philosophy behind it and
[CHANGELOG.md](./CHANGELOG.md) for what has already shipped.

## Release 0.8.4 — Explainable ranking (done)

- [x] Platform icon and name on every row in „Najlepsze materiały”.
- [x] Nullable per-content follower/subscriber gain carried through the generic API, with an explicit „brak danych” fallback.
- [x] Expandable score audit: normalized inputs, weights, points added and points not earned.
- [x] Dedicated „Jak działa punktacja?” page with formula, normalization, limitations and example.
- [x] The same explanation on individual content detail pages.
- [x] Component and scoring regression tests.
- [ ] Integrate YouTube Analytics API before showing per-video subscriber gain; Data API v3 does not provide that attribution.
- [ ] Populate Meta per-content follower gain only if the live Graph API returns a documented direct attribution. Never infer it from account-level changes.

## Release 0.8.3 — Instagram Complete (code complete; live verification pending)

- [x] Exact Instagram permission groups and actionable missing-scope diagnostics.
- [x] Linked Business/Creator discovery through the selected Facebook Page.
- [x] `PlatformAccount` creation plus automatic first synchronization.
- [x] One orchestration path for initial, manual and scheduled Meta sync.
- [x] Cursor-paginated media, comments and replies; resilient per-metric insights.
- [x] Shared content/comment storage and Instagram dashboard/Community states.
- [x] 176 backend tests and clean production frontend build.
- [ ] In Meta's active Login Configuration, grant `instagram_basic`,
      `instagram_manage_comments` and `read_insights`, remove the
      old RCC Business Integration grant, and reconnect.
- [ ] Verify the first and manual sync against the real Instagram account, then
      optionally enable `META_SYNC_ENABLED=true` and observe one scheduled run.

## Release 0.8.1 — Meta Page Selection (done)

Shipped in full — see [CHANGELOG.md](./CHANGELOG.md). A pre-launch audit found
0.8.0's `meta_callback()` silently connected the first Facebook Page returned
by the Meta account, with no way to choose — fixed with a proper Page
Selection screen (ADR-023): OAuth consent fetches every Page (with linked
Instagram resolved), holds them server-side, and requires an explicit pick
before any `PlatformAccount` is written. Also fixed two real bugs found during
credential setup (redirect URI HTTPS-exemption hostname, hardcoded Graph API
version — ADR-022) and added optional Facebook Login for Business
(`META_LOGIN_CONFIG_ID`) support for Meta app types that only expose
Configurations. 153 backend tests pass (75 for the Meta integration
specifically), frontend build clean across 15 routes.

**Known follow-ups (not blockers — see [KNOWN_ISSUES.md](./KNOWN_ISSUES.md)):**
- [ ] Not yet verified against a real Meta account with multiple Pages, or
      against a real Facebook Login for Business Configuration — built and
      tested against fake Graph API responses only.
- [ ] Pending Page Selection state is in-memory/single-process (deliberate,
      see ADR-023) — revisit if RCC ever runs multiple backend workers.

## Release 0.8.0 — Facebook & Instagram (Meta Platform Integration) (done)

Shipped in full — see [CHANGELOG.md](./CHANGELOG.md). Facebook and Instagram
sync into the unified `ContentVideo`/`Publication`/`MetricSnapshot` engine
(finally populated per ADR-003/ADR-020) via one generic `PlatformAdapter`
protocol, sharing the Community Engine (comments, conversation state, quick
replies) and Creator Intelligence engine with YouTube. YouTube's own dedicated
pipeline is untouched; a new dual-write bridge makes its data visible on the
new generic `/platforms/*` surfaces too. 140 backend tests pass (62 new),
frontend build clean across all 14 routes, verified end-to-end against the
real connected YouTube channel.

**Known follow-ups (not blockers, tracked honestly — see
[KNOWN_ISSUES.md](./KNOWN_ISSUES.md)):**
- [x] Facebook is connected and synchronized against the real Meta Page.
- [x] Explicit Page picker replaces the unsafe first-Page behavior (0.8.1).
- [x] Opt-in Facebook/Instagram scheduler reusing the manual path (0.8.3).
- [ ] Complete the real Instagram permission grant/reconnect and verify its
      first sync (tracked under 0.8.3 above).
- [ ] Facebook/Instagram sit at the generic surface's baseline depth (no
      channel-history chart, no data-quality audit, no quota-aware incremental
      sync) — closing that gap to YouTube's full depth is future work.

## Release 0.7.1 — Community UX & Conversation Engine (done)

Shipped in full — see [CHANGELOG.md](./CHANGELOG.md). Fixed the conversation-state
bug (last-message-based, not "any reply ever"), fixed a live-discovered bug where a
channel's own pinned top-level comment was wrongly flagged "needs reply,"
recalculated priority to use the new state + true last-activity recency, added
viewerRating capture + highly-liked highlighting, new filters (state/author) and
sorts (most-replied/recently-active), and polished cards/Home/Video-Detail. 78
backend tests pass, frontend build clean. Verified against the real connected
channel — the account had already been reconnected and had real replies posted
directly on YouTube, which RCC now correctly displays as Resolved.

**Known follow-ups (not blockers, tracked honestly):**
- [ ] "Double-submit protection" for replies is a UI-state guard (composer
      disables while sending) rather than a backend idempotency key — there's no
      natural request-level dedup for arbitrary reply text against the real
      YouTube API. Revisit only if double-posting is observed in practice.
- [ ] No automated visual/responsive browser testing this release either (see the
      same caveat under Sprint 5/6 below) — Community Inbox layouts follow the
      existing 1100px/760px breakpoints but haven't been visually confirmed.
- [ ] "Home" now shows five community-related facts (awaiting reply, new
      questions, resolved, most-discussed video, recently-active discussions) —
      worth a future glance to confirm this hasn't tipped Home over into feeling
      like a second inbox, per the release brief's "not a full comment-management
      screen" instruction. Currently still a compact summary with one link out.

## Release 0.7.0 — YouTube Community Inbox (done)

Shipped in full per the release brief — see [CHANGELOG.md](./CHANGELOG.md) for the
detailed outcome (comment model, quota-conscious sync, Community Inbox, reply/edit/
delete, quick-reply templates, question/priority heuristics, video-detail + Home
integration). The one action item from this release (reconnect for the
`youtube.force-ssl` scope) has been completed by the operator — real comment sync
and real replies are now live on the connected channel.

## Sprint 5 & 6 — Advanced Analytics + Historical Engine (done)

Both sprints shipped in full — see [CHANGELOG.md](./CHANGELOG.md) for the detailed
outcome. Everything originally listed here (sort/filter/video-detail/compare/labels
for Sprint 5; dedup/scheduler/history-bucketing/channel-history/data-quality for
Sprint 6) is complete, tested, and verified against the real connected channel.

**Known follow-ups from this pair of sprints** (not blockers, tracked honestly):
- [ ] The frontend's filter-scoped performance label/score (computed client-side over
      the current filtered set) and the backend's channel-wide label/score
      (`performance_label`/`performance_score` from `/videos`) are two different,
      correctly-labeled numbers that can look inconsistent side by side on the same
      page (e.g. dashboard ranking vs. table). Both are individually correct per
      ADR-005; a future pass could add an explicit "względem czego" tooltip on every
      instance to make the distinction unmissable rather than just documented.
- [ ] `GET /channel/history` and the new subscriber-growth chart only render once
      enough tracking history exists (currently `insufficient: true` for this
      instance — RCC has been tracking under a day). Re-verify the chart's visual
      layout once real multi-day channel history accumulates.
- [ ] No automated visual/responsive testing was performed this pair of sprints
      (no browser tooling available in this session) — verification was HTTP-level
      (status codes + HTML content assertions) plus a full backend test suite.
      A manual pass in an actual browser at desktop/tablet/mobile widths is still
      worth doing before considering the responsive CSS final.

## Sprint 7 (proposed)

**Integrations**
- ~~First real second-platform integration: Facebook.~~ Shipped in Release
  0.8.0, together with Instagram — see above.

**AI**
- First AI Engine narration pass (see [AI_ENGINE.md](./AI_ENGINE.md)): consume
  existing `Recommendation` objects, produce narrated summaries, with hard
  constraints against inventing numbers or asserting causation.

## Sprint 8 (proposed)

**Integrations**
- ~~Instagram integration, same adapter pattern as Facebook.~~ Shipped in
  Release 0.8.0. TikTok remains a future `PlatformAdapter` implementation only
  (ADR-020) — no new tables, sync service, or API router required.
- ~~Once ≥2 platforms are live: finally populate the unified `ContentVideo`/
  `Publication`/`MetricSnapshot` engine for real cross-platform rollups.~~
  Shipped in Release 0.8.0 (ADR-020) — Facebook/Instagram sync directly into it,
  and YouTube dual-writes into it via `youtube_unified_bridge.py`.

## Future

**Product**
- CRM layer linking content/topic performance to leads or clients.
- Multi-workspace support (wire the already-built but unused User/JWT auth into every
  route, scope `PlatformAccount` by workspace).

**Data**
- YouTube Analytics API integration (separate OAuth scope) to unlock the metrics
  Sprint 5's "not available" card currently lists honestly rather than fakes: shares,
  watch time, average view duration, CTR, impressions, traffic sources, per-video
  subscriber gain/loss.

**Housekeeping**
- Decide the fate of the legacy `Reel` model/router (disconnected since before Sprint
  1.1) — confirm unused and remove, or repurpose.
