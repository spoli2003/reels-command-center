# Changelog

Entries are grouped by sprint, newest first. This changelog describes product/
engineering outcomes, not individual commits.

## Sprint 5 — Advanced Analytics & Usability *(in progress)*

Focused on making the existing analytics experience faster and more powerful without
adding new pages: click-to-sort table headers with a persistent 3-state cycle,
richer filtering (min/max view counts, "best/worst/recent/trending" quick presets),
previous/next video navigation with keyboard shortcuts, an honest "not currently
available" card for YouTube metrics that require the (unimplemented) Analytics API,
CSV export from the comparison page, an expanded performance-label taxonomy (🔥 Viral
→ 💀 Dead, deterministic and mutually exclusive), and structured per-video metadata
(`performance_score`, `trend`, `engagement_category`, `growth_category`,
`topic_keywords`) exposed via the existing `/videos` and `/videos/{id}` endpoints in
preparation for a future AI narration layer (no AI implemented).

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
guarantees remain open (see [TODO.md](./TODO.md)).

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
