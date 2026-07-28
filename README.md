# Reels Command Center — Sprint 3

Sprint 3 dodaje produkcyjny fundament lokalny:

- PostgreSQL 16,
- Redis 7,
- migracje Alembic uruchamiane automatycznie,
- rejestrację, logowanie, wylogowanie i endpoint `/api/auth/me`,
- hasła hashowane Argon2,
- sesję JWT w ciasteczku HttpOnly,
- zachowaną integrację YouTube ze Sprintu 2.

## Start

```bash
cp .env.example .env
docker compose up --build
```

Panel: http://127.0.0.1:3000  
API: http://127.0.0.1:8000  
Swagger: http://127.0.0.1:8000/docs

## Testy

```bash
docker compose run --rm backend pytest
```
