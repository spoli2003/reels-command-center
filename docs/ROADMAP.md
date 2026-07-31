# Roadmap

## Vision

See [PRODUCT_VISION.md](./PRODUCT_VISION.md). In one line: RCC turns a creator's raw
platform data into decisions, not just statistics.

## Product principles

- Every feature must improve creator decision-making.
- Creator experience is always more important than technical elegance.
- Never fabricate data — an honest empty state beats a guessed number.
- Every metric, chart, ranking and score explains itself in place.
- Deterministic analytics are the source of truth; AI (when built) narrates them, never invents them.

## Creator-first philosophy

RCC is designed as if the person using it has never written a SQL query and doesn't
want to. Every screen is judged by one question: *if a creator opened this cold, would
they know what to do in the next five seconds?* If the answer is no, the screen isn't
done — no matter how complete the underlying data model is.

## Supported platforms

| Platform | Status | Notes |
|---|---|---|
| YouTube | Live | OAuth (Data API v3), full sync, analytics, Creator Intelligence, Community Inbox (comments) |
| Facebook | Live | Meta OAuth, explicit Page selection, content/comment sync, analytics, Community Inbox |
| Instagram | Code-complete; live grant pending | Business/Creator discovery, first/manual/scheduled sync, Reels/posts, insights, comments and shared dashboard; the live Meta Configuration still needs the Instagram permissions listed in `.env.example`/the UI |
| TikTok | Planned | No integration work started |

The intelligence engine (`backend/app/services/intelligence/`) is already
platform-agnostic — it operates on a generic `ContentItem` shape, not YouTube types.
Adding a platform means writing a thin adapter (like
`youtube_intelligence_adapter.py`), not touching the engine. See
[ARCHITECTURE.md](./ARCHITECTURE.md).

## Current architecture (summary)

FastAPI + SQLAlchemy + PostgreSQL backend, Next.js frontend, Docker Compose for local
development. Full detail in [ARCHITECTURE.md](./ARCHITECTURE.md).

## Development rules

See [CLAUDE.md](./CLAUDE.md) for the full standing instruction set. In short: think
like a product designer and a creator, not only an engineer; never fabricate; always
explain; always test and build before calling work done; prefer reusable architecture
over one-off solutions.

## UX rules

See [UI_GUIDELINES.md](./UI_GUIDELINES.md). In short: cards, rankings, summaries and
actionable recommendations over generic admin-dashboard charts; no empty screens; no
duplicated information; every number tooltipped.

## AI philosophy

No AI is implemented yet. Every sprint so far has deliberately built the deterministic
layer AI will eventually sit on top of — composite scores, trend classification,
confidence-gated recommendations, structured per-video metadata. See
[AI_ENGINE.md](./AI_ENGINE.md) for the intended design once that layer is built.

## Sprint history (long-term roadmap so far)

| Sprint | Theme | Outcome |
|---|---|---|
| 1 | Unified data engine | `ContentVideo`/`Publication`/`MetricSnapshot` model introduced for cross-platform aggregation. Never populated by the YouTube sync path — superseded in practice by the YouTube-specific model; left in place, unused, rather than removed mid-project. |
| 1.1 | YouTube dashboard UX correction | Fixed misleading charts, added filters (date range/search/sort), best/attention video sections, deterministic suggestions. |
| 1.2 | Video navigation & detail pages | Made every displayed video consistently clickable (thumbnail, title, external YouTube link); rebuilt the video detail page (channel baseline, insights, related videos, snapshot history). |
| 3 | Historical engine (planned, not implemented) | A full plan was produced (idempotent snapshot engine, concurrency guard, scheduler) but development moved to Sprint 4 before it was approved. The one piece that *did* ship — per-run channel snapshots (`YoutubeChannelSnapshot`) — landed as part of Sprint 4's subscriber-history work. The scheduler and snapshot-deduplication guarantees remain open — see [TODO.md](./TODO.md). |
| 4 | Creator Intelligence engine | Platform-agnostic recommendation engine (`services/intelligence/`): daily brief, winning/attention videos, topic clustering, publishing patterns, follow-up opportunities, title-pattern analysis — all confidence-gated and explainable. New `/youtube/intelligence` page. |
| 4.1 | Product polish | Home page and Library repurposed to read real YouTube data instead of the empty unified engine; removed low-value charts (scatter, upload-frequency); made sync effects visible (duration, counts, errors) after discovering sync worked but gave no feedback. |
| 5 | Advanced analytics & usability | Click-to-sort tables, richer filtering (min/max views, quick presets), video prev/next navigation, honest "not available" metrics card, CSV export from the comparison page, expanded performance labels, and structured per-video metadata in preparation for the future AI layer. |
| 6 | Historical analytics engine | Idempotent, quota-conscious, crash-tolerant sync (overlap guard, stale-run reclaim, per-video fault isolation), an in-process automatic scheduler, age-anchored history bucketing (day/week/month, never raw sync timestamps), channel-wide history, and a data-quality audit. |
| 0.6.1 | Synchronization consistency (patch) | Fixed a real bug where different pages could show different "last synchronization" timestamps — `GET /status` is now the single source of truth everywhere, with a shared `<SyncStatusLine>` component and `router.refresh()` after sync. |
| 0.7.0 | YouTube Community Inbox | RCC's first module that acts, not just analyzes: review, prioritize, and reply to YouTube comments without leaving RCC. Deterministic (no LLM) likely-question detection and priority scoring, quota-conscious comment sync, own-reply edit/delete with server-side authorization, quick-reply templates, and Home/Video-Detail integration. Requires a one-time OAuth reconnect (new `youtube.force-ssl` scope) for accounts connected before this release. |
| 0.8.0–0.8.2 | Meta foundation and Facebook completion | Shared platform/content/comment layer, Meta OAuth through Facebook Login for Business, explicit Page selection, safe token diagnostics, real Facebook connection and synchronization. Live debugging fixed hostname-scoped OAuth state, secret-bearing exception logs, the missing `business_management` grant and an optional-Instagram lookup crash. |
| 0.8.3 | Instagram Complete | Business and Creator account discovery through the linked Facebook Page; complete permission diagnostics; immediate first sync, manual sync and opt-in scheduler through one orchestration path; cursor-paginated Reels/posts/comments/replies; honest media insights; shared dashboard/Community states. Code and synthetic regression verification complete; live Meta permission grant/reconnect remains an operator step. |
| 0.8.4a | Explainable cross-platform ranking | Rebuilt „Najlepsze materiały” with a platform badge, honest per-item audience-gain availability, an expandable audit of the existing 50/30/20 score, detail-page breakdowns and a dedicated scoring methodology FAQ. |
| 0.8.4b | Unified Platform Experience | Unified the YouTube/Facebook/Instagram navigation and section layout, added the missing YouTube Materials surface, removed synchronization cards from dashboards, introduced a dedicated synchronization center with history/schedules/errors, an aggregate `Synchronizuj wszystko` action, and a shared platform-status strip. TikTok is represented only as an honest planned adapter. |

## Definition of Done

A sprint (or any change) is done when:

- Backend tests pass (`docker compose run --rm backend pytest`).
- Frontend production build succeeds (`docker compose build frontend && ... npm run build`).
- Every affected page has been verified against the real connected channel, not just
  synthetic test data.
- No fabricated numbers were introduced — every new metric traces to a real,
  documented calculation or an honest empty/unavailable state.
- The change was reviewed once more for unnecessary UI, duplicated information, and
  unclear wording before being reported as finished.

## Success metric

**A creator should be able to open RCC and know, within five seconds, what happened
and what deserves their attention next.** Every roadmap decision is weighed against
whether it moves RCC closer to or further from that five-second bar.
