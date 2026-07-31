"""Short-lived, server-side state for Meta Page selection.

The OAuth callback and the picker are separate HTTP requests.  Keeping the
candidate Pages in a module-level dictionary made the flow lose its state on
every uvicorn reload (and would also fail with more than one worker).  Runtime
state therefore lives in Redis with a ten-minute TTL.  Tests use the small
in-memory implementation below so they do not require an external service.

Only an opaque random ``selection_id`` is sent to the browser.  Page access
tokens are encrypted before they reach this service by the caller.
"""

from __future__ import annotations

import json
import secrets
import time
from functools import lru_cache
from typing import Any, Optional

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

_TTL_SECONDS = 600
_KEY_PREFIX = "rcc:meta:pending-selection:"
_memory_store: dict[str, dict[str, Any]] = {}


class PendingSelectionStoreError(RuntimeError):
    """Redis could not persist or read the OAuth hand-off state."""


@lru_cache(maxsize=4)
def _redis_client(redis_url: str) -> Redis:
    return Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def _uses_memory_store(now: Optional[float] = None) -> bool:
    # ``now`` is an explicit deterministic-test hook retained for the service's
    # TTL tests.  Normal application requests always use Redis.
    return now is not None or get_settings().environment.lower() == "test"


def _key(selection_id: str) -> str:
    return f"{_KEY_PREFIX}{selection_id}"


def _prune_expired(now: Optional[float] = None) -> None:
    current = now if now is not None else time.time()
    expired = [key for key, entry in _memory_store.items() if entry["expires_at"] <= current]
    for key in expired:
        _memory_store.pop(key, None)


def _decode(raw: str | bytes | None) -> Optional[dict[str, Any]]:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        entry = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise PendingSelectionStoreError("Uszkodzony stan wyboru Meta w Redis.") from exc
    if not isinstance(entry, dict) or "target" not in entry or not isinstance(entry.get("pages"), list):
        raise PendingSelectionStoreError("Nieprawidłowy stan wyboru Meta w Redis.")
    return entry


def create_selection(target: str, pages: list[dict[str, Any]], now: Optional[float] = None) -> str:
    current = now if now is not None else time.time()
    selection_id = secrets.token_urlsafe(24)
    entry = {"target": target, "pages": pages, "expires_at": current + _TTL_SECONDS}

    if _uses_memory_store(now):
        _prune_expired(current)
        _memory_store[selection_id] = entry
        return selection_id

    try:
        stored = _redis_client(get_settings().redis_url).set(
            _key(selection_id),
            json.dumps(entry, ensure_ascii=False, separators=(",", ":")),
            ex=_TTL_SECONDS,
        )
    except RedisError as exc:
        raise PendingSelectionStoreError("Nie udało się zapisać wyboru Strony w Redis.") from exc
    if not stored:
        raise PendingSelectionStoreError("Redis nie zapisał wyboru Strony Meta.")
    return selection_id


def get_selection(selection_id: str, now: Optional[float] = None) -> Optional[dict[str, Any]]:
    """Read without consuming so a failed choice can be retried."""
    current = now if now is not None else time.time()
    if _uses_memory_store(now):
        _prune_expired(current)
        return _memory_store.get(selection_id)

    try:
        return _decode(_redis_client(get_settings().redis_url).get(_key(selection_id)))
    except RedisError as exc:
        raise PendingSelectionStoreError("Nie udało się odczytać wyboru Strony z Redis.") from exc


def consume_selection(selection_id: str, now: Optional[float] = None) -> Optional[dict[str, Any]]:
    """Atomically read and remove a successfully used selection."""
    current = now if now is not None else time.time()
    if _uses_memory_store(now):
        _prune_expired(current)
        return _memory_store.pop(selection_id, None)

    try:
        return _decode(_redis_client(get_settings().redis_url).getdel(_key(selection_id)))
    except RedisError as exc:
        raise PendingSelectionStoreError("Nie udało się zamknąć wyboru Strony w Redis.") from exc
