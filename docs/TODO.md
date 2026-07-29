# TODO

Grouped by timeframe, then by category. This is the working roadmap — see
[ROADMAP.md](./ROADMAP.md) for the philosophy behind it and
[CHANGELOG.md](./CHANGELOG.md) for what has already shipped.

## Sprint 5 (remaining)

**Backend**
- [x] Composite score, engagement/growth categories, and the 7-state performance
      label ported to `content_metrics.py`.
- [x] `/videos` and `/videos/{id}` extended with structured per-video metadata
      (views/day, engagement rate, trend, score, label, categories, topic keywords).
- [ ] Test coverage for the new metadata fields and label priority ordering.

**Frontend**
- [ ] Click-to-sort table headers (3-state: asc → desc → default), extended sort keys
      (score, age, duration, title), sort state persisted in the URL.
- [ ] Advanced filter bar: min/max views, "best/worst/recent/trending" quick presets.
- [ ] Video detail: previous/next navigation, back-to-filtered-list, keyboard
      shortcuts.
- [ ] Honest "not currently available" metrics card (shares, watch time, CTR,
      impressions, traffic sources, per-video subscriber attribution).
- [ ] Compare page: sortable table view, average/median deltas, CSV export.
- [ ] Performance-label badges wired into the Library table, "Wszystkie filmy," and
      the video detail hero.
- [ ] "Metadane techniczne" section and the "AI analysis coming later" placeholder on
      the video detail page.

**Verification**
- [ ] Full backend test run + frontend production build + manual pass on every page
      against the real connected channel before closing out the sprint.

## Sprint 6 (proposed)

**Backend / Reliability**
- Build the Sprint 3 historical engine properly: one shared timestamp per sync run, a
  database-level uniqueness constraint preventing duplicate snapshots per run, and
  per-video fault isolation (a savepoint per video so one bad API response doesn't
  roll back the whole run).
- Automatic sync scheduler: a separate Docker service, `YOUTUBE_SYNC_ENABLED` /
  `YOUTUBE_SYNC_INTERVAL_HOURS` env config, a concurrency guard with staleness
  self-healing, safe-by-default (disabled unless explicitly enabled).

**Integrations**
- First real second-platform integration: Facebook. Reuse the `PlatformAccount`
  pattern; write a `facebook_intelligence_adapter.py` following the YouTube adapter's
  shape — no changes expected inside `services/intelligence/`.

## Sprint 7 (proposed)

**Integrations**
- Instagram and TikTok integrations, same adapter pattern as Facebook.
- Once ≥2 platforms are live: finally populate the unified `ContentVideo`/
  `Publication`/`MetricSnapshot` engine for real cross-platform rollups (it has sat
  unused since Sprint 1 — see [DATABASE.md](./DATABASE.md)).

**AI**
- First AI Engine narration pass (see [AI_ENGINE.md](./AI_ENGINE.md)): consume
  existing `Recommendation` objects, produce narrated summaries, with hard
  constraints against inventing numbers or asserting causation.

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
