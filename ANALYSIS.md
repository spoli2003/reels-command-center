# RCC Architecture Analysis

## 1. Current Architecture

**Stack:** FastAPI (Python 3.12) + SQLAlchemy 2.0 + Alembic + PostgreSQL 16 + Redis 7 (provisioned, unused) backend; Next.js 15 / React 19 App Router frontend. Dockerized via `docker-compose` (db, redis, backend, frontend). Single `.env` drives config through `pydantic-settings`.

**Request flow:** Next.js server components (`page.tsx`, `videos/page.tsx`, `videos/[id]/page.tsx`) do server-side `fetch` against the backend at build/request time (`INTERNAL_API_URL`, i.e. the Docker service name) and render read-only pages. One client component (`youtube-panel.tsx`) talks directly to the browser-exposed `NEXT_PUBLIC_API_URL` for the YouTube integration panel (status/sync/disconnect). There is no shared API client, no data-fetching hook, no client-side state library — every page duplicates its own `fetch` + try/catch.

**Backend is organized in fairly clean layers:**
- `api/` — FastAPI routers (`auth`, `reels`, `youtube`, `content`, `health`), thin, call into `db`/`services` directly.
- `models/` — SQLAlchemy ORM (`user`, `reel`, `integration`, `content`).
- `schemas/` — Pydantic I/O contracts, mostly one-to-one with routers.
- `services/` — `token_crypto` (Fernet envelope encryption for OAuth tokens) and `youtube_sync` (the only real business-logic module).
- `integrations/youtube/` — thin wrapper around `googleapiclient` + `google-auth-oauthlib`, PKCE OAuth flow, ISO-8601 duration parsing.
- `core/` — settings (env-driven) and security (Argon2 hashing via `pwdlib`, JWT via `PyJWT`).
- `db/` — engine/session factory, declarative `Base`.

**Two parallel data models coexist**, described more below: a **YouTube-specific schema** (`PlatformAccount → YoutubeChannel → YoutubeVideo → YoutubeMetricSnapshot`, plus `SyncRun`) that the OAuth/sync pipeline actually writes to, and a **"unified content engine"** (`ContentVideo → Publication → MetricSnapshot`) that the docs (`ARCHITECTURE.md`, `DATABASE.md`) describe as canonical and that the frontend actually reads from. **These two are not connected** — `sync_youtube()` never writes a `ContentVideo`/`Publication`/`MetricSnapshot` row, so a YouTube sync populates data the dashboard/library UI can never see, and the "add a video" flow only reaches the unified engine (currently only reachable via Swagger, since the frontend has no create form).

**Auth is a fully-built, entirely disconnected subsystem.** `users` table, Argon2 hashing, JWT-in-HttpOnly-cookie session, `/api/auth/register|login|logout|me` all exist and are tested — but no other router (`content`, `youtube`, `reels`) depends on `get_current_user`, and the frontend has no login/register page at all. Every resource in the system (`ContentVideo`, `PlatformAccount`, etc.) is global with no `user_id`/owner column, so today RCC is a single-tenant app with a bolted-on, unused auth layer.

**Migrations:** two Alembic revisions, additive only (`0001_initial`, `0002_unified_content_engine`), consistent with the models. No down-migration has been exercised, no data-migration between the YouTube-specific and unified tables exists.

**Docker/infra:** `docker-compose.yml` is the only deployment artifact — dev-oriented (`--reload`, bind-mounted backend volume, hardcoded dev Postgres password, `infra/` directory exists but is empty). No CI config, no production Dockerfile/compose override, no health checks beyond Postgres readiness.

---

## 2. Technical Debt

1. **Unenforced auth** — every content/integration endpoint is unauthenticated and unscoped; anyone who can reach the API can read/write/delete everything. The JWT/cookie infra exists but nothing checks it outside `/api/auth/me`.
2. **Two unsynced data pipelines** for the same concept (video + metrics) — YouTube sync writes to `integration.py` tables; the UI reads from `content.py` tables. A user who connects and syncs YouTube sees **zero** results in the dashboard/library.
3. **Legacy `Reel` model/router/schema** (`reels.py`, `models/reel.py`, `schemas/reel.py`) is disconnected from everything else — no relation to `ContentVideo`, no frontend usage, not covered by the "unified engine" narrative. Looks like a Sprint-1 leftover never removed.
4. **Redis provisioned but never imported** anywhere in `app/` — pure config/infra dead weight (`redis==6.2.0` in requirements, service in compose, `redis_url` in settings, nothing consumes it). No caching, no queue, no rate limiting.
5. **No background job runner** — `sync()` runs YouTube's paginated API calls synchronously inside an HTTP request; for a channel with hundreds of videos this will be slow and is a timeout/retry risk with no idempotency guard beyond upsert-by-`youtube_video_id`.
6. **No pagination** on `/api/content/videos` or `/api/integrations/youtube/videos` (latter hardcoded `.limit(200)`) — will degrade linearly as libraries grow.
7. **Frontend "+ Nowy film" button links to `/`**, not to any creation form — there is no UI path to create a `ContentVideo` or a `Publication`; only Swagger/curl can do it. The unified engine is API-only right now.
8. **Duplicated page shells** — the sidebar/nav markup is copy-pasted verbatim across `page.tsx`, `videos/page.tsx`, `videos/[id]/page.tsx` instead of a shared layout/component.
9. **No typed/shared API client** on the frontend — three separate hand-rolled `fetch` + try/catch blocks, inconsistent error handling (silent `[]`/`null` fallback vs. thrown `Error` in `youtube-panel.tsx`).
10. **Hardcoded dev secrets** in compose/`.env.example` (`rcc_dev_password`, "change-me" secrets) with no documented production secret-management story.
11. **`google_client_secret.json` committed as a real file** at `backend/secrets/google_client_secret.json` (not just `.gitkeep`) — worth confirming it's a placeholder/test fixture and not a real credential before this repo goes anywhere public.
12. **No CI pipeline** — `pytest`/`ruff` exist and work (`make test`, `make lint`) but nothing runs them automatically.
13. **Cookie is `secure=False` unconditionally** in `auth.py` (`set_cookie`) — fine for local HTTP dev, but there's no environment-conditional flip for production, so it'd ship insecure by default.
14. **Tests hit a real SQLite file** (`sqlite:///./test-rcc.db`) with no fixture teardown/isolation between runs — state can leak across test runs (e.g. `test_content.py`'s create/list assumes no interference from prior runs).
15. **No `updated_at`/soft-delete** on `Publication`/`MetricSnapshot`, and `Publication` deletion is only reachable indirectly (no direct DELETE endpoint) once `ContentVideo` grows publications.

---

## 3. Duplicated Models

The core duplication is a **parallel video/metrics hierarchy**:

| Unified Content Engine (`content.py`, docs' canonical model) | YouTube-specific (`integration.py`, what sync actually populates) |
|---|---|
| `ContentVideo` | `YoutubeVideo` |
| `Publication` (per-platform upload record) | *(implicit — one `YoutubeVideo` per channel, no cross-platform concept)* |
| `MetricSnapshot` (immutable, generic: views/reach/impressions/likes/comments/shares/saves/watch_time/followers) | `YoutubeMetricSnapshot` (immutable, narrower: views/likes/comments only) |
| — | `YoutubeChannel` (channel-level stats: subscribers/views/videos — no unified equivalent) |
| — | `SyncRun` (sync audit log — no unified equivalent) |

Also **`Reel`** (`models/reel.py`: title/category/hook) is a third, independent "content idea" concept with its own CRUD router — not a duplicate schema of `ContentVideo` exactly (it's more of a planning/ideation record), but it overlaps conceptually and isn't linked to it at all. It reads as an earlier iteration of "a piece of content" superseded by `ContentVideo` but never removed or migrated.

**Net effect:** three uncoordinated notions of "a video" (`Reel`, `YoutubeVideo`, `ContentVideo`) and two uncoordinated notions of "metrics over time" (`YoutubeMetricSnapshot`, `MetricSnapshot`).

---

## 4. Missing Abstractions

- **No sync → unified-engine bridge.** There's no service that takes `YoutubeChannel`/`YoutubeVideo`/`YoutubeMetricSnapshot` output and materializes/upserts it into `ContentVideo`/`Publication`/`MetricSnapshot`. This is the single biggest gap given the roadmap explicitly plans Meta and TikTok next — without this abstraction, each new platform will spawn its own disconnected `Platform*` table family instead of feeding the unified model the whole system was designed around.
- **No `PlatformIntegration` interface/protocol.** `youtube_sync.py` is hand-written against the YouTube client concretely. Nothing defines a common contract (`connect`, `sync`, `disconnect`, `list_videos`) that Meta/TikTok integrations would implement, even though `docs/ROADMAP.md` commits to adding them.
- **No authorization/ownership layer.** No `user_id` on `PlatformAccount`/`ContentVideo`, no dependency like `get_current_user` wired into non-auth routers, no concept of "this account belongs to this user."
- **No repository/query layer** — routers embed SQLAlchemy `select()` statements directly; fine at this size but will duplicate as more read patterns appear (e.g. the `_statement()` helper in `content.py` is already router-local rather than shared).
- **No frontend API client/data layer** — no `lib/api.ts`, no typed fetch wrapper, no shared error/loading UI pattern.
- **No background task abstraction** — no Celery/RQ/arq despite Redis being provisioned for exactly this purpose; sync is a blocking HTTP call.
- **No environment-aware config split** (dev vs. prod settings, e.g. cookie `secure` flag, CORS, debug/reload) — one `Settings` class with dev defaults used everywhere.
- **No pagination/cursor abstraction** for list endpoints.
- **No shared "connected platform" UI abstraction on the frontend** — `youtube-panel.tsx` is fully bespoke; adding Meta/TikTok panels will copy-paste it rather than reuse a generic `PlatformIntegrationPanel`.

---

## 5. Suggested Improvements

**Priority 1 — fix the core data-flow break:**
- Add a bridge in `youtube_sync.py` (or a new `services/unified_sync.py`) that upserts a `ContentVideo` + `Publication` + `MetricSnapshot` per synced YouTube video, keyed via `Publication(platform="youtube", external_id=youtube_video_id)`. This is the fix that actually makes the "unified data engine" the roadmap describes real.
- Decide the fate of the YouTube-specific tables: either treat them purely as a raw-ingestion cache feeding the bridge above (keep, but document the relationship), or fold their fields into `Publication`/`MetricSnapshot` and drop them. Given Meta/TikTok are coming, I'd lean toward keeping a thin per-platform raw table only if the platform API shape genuinely needs it, with the bridge being mandatory.
- Retire `Reel` (model, router, schema, migration) unless it serves a distinct "content idea/planning" purpose the user still wants — if so, rename/reposition it explicitly rather than leaving it looking like an abandoned duplicate of `ContentVideo`.

**Priority 2 — decide on auth's scope:**
- Either wire `get_current_user` into `content`/`youtube` routers and add `user_id` ownership to `PlatformAccount`/`ContentVideo` (turning this into the multi-tenant app the auth system implies), or explicitly document RCC as single-user/local-only and consider whether the JWT/cookie/Argon2 machinery is worth keeping vs. simplifying. Right now it's neither — built but inert.

**Priority 3 — platform-integration abstraction ahead of Meta/TikTok:**
- Define a small `PlatformIntegration` protocol (connect/callback/sync/disconnect/list) before writing Meta's integration, so the second platform doesn't duplicate `youtube.py`'s router shape wholesale.

**Priority 4 — operational hygiene:**
- Move sync execution off the request thread (Redis-backed queue, since Redis is already provisioned — or remove Redis if not needed).
- Add pagination to list endpoints.
- Add a CI workflow running `pytest` + `ruff` on push/PR.
- Environment-conditional cookie `secure` flag and CORS config.
- Confirm `backend/secrets/google_client_secret.json` is a non-sensitive fixture; if real, remove from git and rotate.

**Priority 5 — frontend structural cleanup:**
- Extract the shared sidebar/shell into a layout component instead of copy-pasting markup across three pages.
- Add a thin typed API client (`lib/api.ts`) shared by server and client components.
- Build the missing "create video / add publication" UI so the unified engine is reachable without Swagger.
