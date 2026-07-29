# Changelog

Entries are grouped by sprint, newest first. This changelog describes product/
engineering outcomes, not individual commits.

## Sprint 6 — Historical Analytics Engine

Turned the sync path from "runs manually, hopefully without duplicating data" into a
real historical engine. Audited `youtube_sync.py` and found two genuine gaps: nothing
stopped two overlapping syncs from both writing near-identical snapshots, and nothing
recovered a `SyncRun` left stuck in `"running"` by a crash/restart. Fixed both: an
overlap guard rejects a sync while another is genuinely in flight (`409`), a stale
`"running"` row older than 30 minutes is reclaimed as failed, and a snapshot is
skipped as a duplicate if the same video/channel already has one younger than 5
minutes — verified against the real connected channel (a second immediate sync
correctly produced `snapshots_created: 0`, `snapshots_deduplicated: 36`). Added
per-video fault isolation via a SQL savepoint per video, so one bad API response
marks that video failed (`status: "partial"`) instead of rolling back the whole run —
this closes the Sprint 3 backlog item. Added an in-process automatic scheduler
(`YOUTUBE_SYNC_ENABLED` / `YOUTUBE_SYNC_INTERVAL_HOURS`, default 6h, disabled unless
explicitly enabled per ADR-009) — deliberately a background asyncio task inside the
existing backend container rather than a new Docker service, to avoid adding
infrastructure a single-tenant tool doesn't yet need. History charts (video and
channel) now bucket by age instead of raw sync timestamps — under 30 days shows one
point per day since publish, 30–180 days one point per week, over 180 days one point
per month — with an honest empty state when fewer than two periods exist, instead of
a jagged chart of near-identical synchronization points. Added a video-detail
timeline (publish → first sync → snapshots → latest sync), velocity/acceleration/
peak-growth/largest-slowdown numbers, a channel-wide history endpoint (subscribers/
views/videos), and a data-quality audit that checks for exact-duplicate snapshots
(auto-repaired), impossible timestamps, and non-monotonic view drops (reported only —
a real one was found on the connected channel, a legitimate YouTube-side correction,
not a bug). No AI implemented; the new velocity/acceleration/growth fields are
deterministic inputs for a future AI layer, same as Sprint 5's metadata.

## Sprint 5 — Advanced Analytics & Usability

Made the existing analytics experience faster and more powerful without adding new
pages. Every video table now supports click-to-sort headers with a persistent
3-state cycle (desc → asc → default), extended to score/age/duration/title, with
sort state kept in the URL. Filtering gained min/max view-count bounds and a
"best/worst/recent/trending" quick-filter row (best/worst adapt to the current
set's own score distribution — 70th/30th percentile — not a fixed threshold). The
video detail page gained previous/next navigation (with arrow-key shortcuts),
a `?from=` back-to-filtered-list link, an honest "not currently available" card
listing exactly which YouTube Analytics API metrics RCC doesn't have (never fake
zeros), and a reserved "AI Summary" card with the literal required placeholder text.
The comparison page gained a sortable table view (alongside the existing cards),
whole-channel median/average/best-ever baselines per metric (not just the compared
set), and a semicolon-delimited CSV export. A 7-tier performance-label taxonomy
(🔥 Viral → 💀 Dead, priority-ordered so a video is never tagged as two contradictory
states) is now computed once on the backend and shown identically everywhere — Library
table, "Wszystkie filmy," compare cards/table, and the video-detail hero. Every video
now exposes structured, deterministic metadata (`performance_score`, `trend`,
`engagement_category`, `growth_category`, `topic_keywords`, plus Sprint 6's
velocity/acceleration/gain fields) via the existing `/videos` and `/videos/{id}`
endpoints, shown in a new "Metadane techniczne" section — preparation for a future AI
narration layer; no AI implemented.

## Sprint 4.1 — Product Polish

Reframed RCC around "what should I do today" instead of "here are statistics." The
Home page was rebuilt from a mostly-empty landing screen (reading from the unused
unified content engine) into a real command center: today's summary, best video,
biggest opportunity, sync status, platform overview, latest uploads, and quick
actions — all sourced from real YouTube data. The video Library was repointed at real
YouTube videos (previously showed zero despite 35 imported videos being visible
elsewhere — a wiring bug, not a sync failure). Removed the views-vs-likes scatter plot
and the upload-frequency bar chart once Creator Intelligence's publishing-pattern
section made them redundant. Diagnosed and fixed sync's "no visible effect" complaint:
sync was always working, it just never reported what it did — `SyncRun` now records
videos discovered/updated, snapshots created, and duration, surfaced in the UI.

## Sprint 4 — Creator Intelligence Engine

Built the platform-agnostic recommendation engine (`backend/app/services/intelligence/`)
that RCC's "Co dalej?" page is built on: a daily brief, winning/attention video
detection, automatic topic clustering from title keywords (no fixed taxonomy —
adapts to any channel), publishing-pattern analysis (best weekday/hour/cadence,
streaks), follow-up opportunity detection, and title-pattern comparison — every
recommendation confidence-gated and tied to real supporting numbers, never asserting
causation. Also corrected a misleading "average views/day" metric that would have
silently used YouTube account age (including years of dormancy) instead of the age of
the oldest *tracked* video.

## Sprint 3 — Historical Engine *(planned, partially absorbed)*

A full plan was produced for an idempotent snapshot engine (one timestamp per sync
run, a database-level uniqueness guarantee against duplicate snapshots, per-video
fault isolation, a Docker-based scheduler) but was not approved/implemented before
work moved to Sprint 4. The one concrete piece that shipped — per-run channel-level
snapshots (`YoutubeChannelSnapshot`), enabling subscriber-count history — landed as
part of Sprint 4's daily-brief work instead. The scheduler and full idempotency
guarantees were later delivered in Sprint 6.

## Sprint 1.2 — Video Navigation & Detail Pages

Audited every place a video is displayed across the app and closed the gaps: metric
comparison rows and compare-page summary badges had no navigation at all; compare
cards and the "all videos" table only linked their title text, not their thumbnail.
Added a consistent pattern (thumbnail + title as one internal link, a small separate
external-YouTube-link action, always as siblings — never nested anchors) and rebuilt
the video detail page around it: full metadata, expandable description, "Obejrzyj na
YouTube" + copy-link actions, a channel-baseline comparison section, deterministic
per-video insights, related videos by shared title keywords, and a snapshot-history
table with deltas.

## Sprint 1.1 — YouTube Dashboard UX Correction

The redesigned dashboard from Sprint 1 wasn't understandable within five seconds: bars
without labels, unexplained scores, no way to filter or search. Rebuilt around
readable ranked lists instead of anonymous charts, added date-range/search/sort
filtering (persisted in the URL), a transparent composite performance score (50%
views/day + 30% engagement + 20% total views, explicitly labeled as relative to the
current filter — never a universal score), a "videos requiring attention" section
comparing against the channel median, and deterministic, non-AI suggestions.

## Sprint 1 — Unified Data Engine

Introduced `ContentVideo`/`Publication`/`MetricSnapshot` as a cross-platform
aggregation model, intended to let one piece of content roll up performance across
YouTube, Facebook, Instagram, and TikTok without overwriting history. The YouTube sync
path was never wired to populate it, so in practice this model has remained an
unused, working API surface throughout every subsequent sprint — documented honestly
in [DATABASE.md](./DATABASE.md) rather than removed or hidden.
