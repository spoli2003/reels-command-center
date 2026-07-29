# TODO

Grouped by timeframe, then by category. This is the working roadmap — see
[ROADMAP.md](./ROADMAP.md) for the philosophy behind it and
[CHANGELOG.md](./CHANGELOG.md) for what has already shipped.

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
- First real second-platform integration: Facebook. Reuse the `PlatformAccount`
  pattern; write a `facebook_intelligence_adapter.py` following the YouTube adapter's
  shape — no changes expected inside `services/intelligence/`. Sprint 6's sync
  engine improvements (dedup, overlap guard, per-video fault isolation, scheduler)
  are platform-agnostic at the `SyncRun`/`PlatformAccount` level, so Facebook's sync
  path can follow the same pattern rather than reinventing it.

**AI**
- First AI Engine narration pass (see [AI_ENGINE.md](./AI_ENGINE.md)): consume
  existing `Recommendation` objects, produce narrated summaries, with hard
  constraints against inventing numbers or asserting causation.

## Sprint 8 (proposed)

**Integrations**
- Instagram and TikTok integrations, same adapter pattern as Facebook.
- Once ≥2 platforms are live: finally populate the unified `ContentVideo`/
  `Publication`/`MetricSnapshot` engine for real cross-platform rollups (it has sat
  unused since Sprint 1 — see [DATABASE.md](./DATABASE.md)).

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
