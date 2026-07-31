# Reels Command Center — local development

RCC is a local multi-platform content analytics workspace for YouTube,
Facebook and Instagram. The current release includes historical metrics,
Creator Intelligence, Community Inbox, Meta Page selection and complete
Instagram Business/Creator synchronization.

## Local stack

- FastAPI + SQLAlchemy + PostgreSQL 16
- Next.js + TypeScript
- Redis 7
- Docker Compose

## Start

```bash
cp .env.example .env
docker compose up --build
```

Use `localhost` consistently for the Meta flow:

- Panel: http://localhost:3000
- API: http://localhost:8000
- Swagger: http://localhost:8000/docs

Do not mix `localhost` and `127.0.0.1` in Meta URLs: the OAuth session cookie
is host-scoped. See [Meta setup](./docs/META_SETUP.md) for the complete local
Configuration and reconnect procedure.

## Verification

```bash
docker compose exec -T backend pytest -q
docker compose build frontend
docker compose run --rm frontend npm run build
```

## Data model

Facebook and Instagram write directly into the shared
`ContentVideo`/`Publication`/`MetricSnapshot` and Community tables. YouTube's
mature dedicated pipeline remains intact and mirrors into this shared layer.
Architecture and product decisions are documented under [`docs/`](./docs/).
