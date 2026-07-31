#!/bin/sh
set -e
alembic upgrade head
# OAuth callbacks carry one-time authorization codes and CSRF state in the
# query string. Uvicorn's default access log prints the complete request target,
# so keep application diagnostics but disable raw access logging to prevent
# those credentials from being copied into Docker logs.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --no-access-log
