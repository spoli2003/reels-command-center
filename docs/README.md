# Reels Command Center (RCC)

**Content Operating System for creators.**

RCC is not a statistics dashboard. It is a decision-support system that helps creators
understand:

- what happened,
- why it happened,
- what deserves attention,
- what to publish next.

Every screen is built to answer those four questions using the creator's own historical
data — never fabricated numbers, never a chart for its own sake.

## Current platform support

| Platform | Status |
|---|---|
| YouTube | ✅ Live — OAuth connect, sync, full analytics, Creator Intelligence |
| Facebook | Planned |
| Instagram | Planned |
| TikTok | Planned |

## Technology

- **Backend:** FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL 16, Redis 7 (provisioned, not yet consumed)
- **Frontend:** Next.js 15 (App Router), React 19, Recharts
- **Infrastructure:** Docker Compose (local development)

## Getting started

```bash
cp .env.example .env
docker compose up --build
```

- Panel: http://127.0.0.1:3000
- API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs

```bash
docker compose run --rm backend pytest      # backend tests
docker compose build frontend && docker compose run --rm frontend npm run build   # frontend production build
```

> The frontend service has no volume mount — rebuild the image (`docker compose build frontend`)
> after any frontend file change before running `npm run build`, or the container will build
> against stale sources.

## Documentation

All project documentation lives in `/docs`:

| File | Purpose |
|---|---|
| [PRODUCT_VISION.md](./PRODUCT_VISION.md) | Why RCC exists and what it optimizes for |
| [ROADMAP.md](./ROADMAP.md) | Principles, philosophy, sprint history, long-term plan |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System design, data flow, backend/frontend structure |
| [CLAUDE.md](./CLAUDE.md) | Standing instructions for AI-assisted development on this repo |
| [UI_GUIDELINES.md](./UI_GUIDELINES.md) | Visual and interaction design rules |
| [AI_ENGINE.md](./AI_ENGINE.md) | Design for the future (not yet built) AI explanation layer |
| [DATABASE.md](./DATABASE.md) | Data model — current and planned |
| [CHANGELOG.md](./CHANGELOG.md) | What shipped, sprint by sprint |
| [TODO.md](./TODO.md) | Active and future work, grouped by category |
