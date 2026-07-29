# TODO

Grouped by timeframe, then by category. This is the working roadmap — see
[ROADMAP.md](./ROADMAP.md) for the philosophy behind it and
[CHANGELOG.md](./CHANGELOG.md) for what has already shipped.

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
