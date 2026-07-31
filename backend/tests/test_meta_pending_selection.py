"""Short-lived Meta selection state: Redis in runtime, memory in tests."""

from app.services import meta_pending_selection


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.last_ttl = None

    def set(self, key, value, ex=None):
        self.values[key] = value
        self.last_ttl = ex
        return True

    def get(self, key):
        return self.values.get(key)

    def getdel(self, key):
        return self.values.pop(key, None)


def test_create_and_get_selection_round_trip():
    pages = [{"id": "page-1", "name": "Strona testowa"}]
    selection_id = meta_pending_selection.create_selection("facebook", pages)

    entry = meta_pending_selection.get_selection(selection_id)
    assert entry is not None
    assert entry["target"] == "facebook"
    assert entry["pages"] == pages


def test_get_selection_does_not_consume_it():
    pages = [{"id": "page-1", "name": "Strona testowa"}]
    selection_id = meta_pending_selection.create_selection("instagram", pages)

    assert meta_pending_selection.get_selection(selection_id) is not None
    assert meta_pending_selection.get_selection(selection_id) is not None  # still there the second time


def test_consume_selection_removes_it():
    pages = [{"id": "page-1", "name": "Strona testowa"}]
    selection_id = meta_pending_selection.create_selection("facebook", pages)

    consumed = meta_pending_selection.consume_selection(selection_id)
    assert consumed is not None
    assert meta_pending_selection.get_selection(selection_id) is None
    assert meta_pending_selection.consume_selection(selection_id) is None


def test_unknown_selection_id_returns_none():
    assert meta_pending_selection.get_selection("does-not-exist") is None
    assert meta_pending_selection.consume_selection("does-not-exist") is None


def test_selection_id_is_unique_per_call():
    pages = [{"id": "page-1", "name": "Strona testowa"}]
    first = meta_pending_selection.create_selection("facebook", pages)
    second = meta_pending_selection.create_selection("facebook", pages)
    assert first != second


def test_expired_selection_is_pruned():
    pages = [{"id": "page-1", "name": "Strona testowa"}]
    now = 1_000_000.0
    selection_id = meta_pending_selection.create_selection("facebook", pages, now=now)

    still_fresh = meta_pending_selection.get_selection(selection_id, now=now + 60)
    assert still_fresh is not None

    expired = meta_pending_selection.get_selection(selection_id, now=now + meta_pending_selection._TTL_SECONDS + 1)
    assert expired is None


def test_runtime_selection_survives_process_memory_reset(monkeypatch):
    """Regression: uvicorn reload between callback and picker must not lose state."""
    fake_redis = FakeRedis()
    monkeypatch.setattr(meta_pending_selection, "_uses_memory_store", lambda now=None: False)
    monkeypatch.setattr(meta_pending_selection, "_redis_client", lambda redis_url: fake_redis)

    pages = [{"id": "page-ig", "name": "Instagram Page", "instagram": {"id": "ig-1"}}]
    selection_id = meta_pending_selection.create_selection("instagram", pages)

    # This is what a backend reload did to the old implementation.
    meta_pending_selection._memory_store.clear()

    entry = meta_pending_selection.get_selection(selection_id)
    assert entry is not None
    assert entry["target"] == "instagram"
    assert entry["pages"] == pages
    assert fake_redis.last_ttl == meta_pending_selection._TTL_SECONDS

    assert meta_pending_selection.consume_selection(selection_id) is not None
    assert meta_pending_selection.get_selection(selection_id) is None
