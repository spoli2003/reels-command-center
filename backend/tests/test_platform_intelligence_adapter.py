"""Release 0.8.0 — content_intelligence_adapter.py (ADR-020/ADR-007). Verifies
Facebook/Instagram publications get real Creator Intelligence output (daily
brief, winning/attention videos, topics, publishing) through the SAME engine
YouTube uses, with zero platform-specific code inside intelligence/, and that
the generic per-video history endpoint buckets correctly."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.integration import PlatformAccount
from app.services.content_intelligence_adapter import get_platform_intelligence_report, get_platform_video_history
from app.services.content_sync import sync_platform_content
from app.services.platforms.base import RawContentItem

NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)


def _item(external_id, views, days_ago):
    return RawContentItem(
        external_id=external_id,
        title=f"Materiał {external_id}",
        description="",
        url=f"https://example.test/{external_id}",
        published_at=NOW - timedelta(days=days_ago),
        thumbnail_url=None,
        duration_seconds=None,
        views=views,
        likes=int(views * 0.05),
        comments=int(views * 0.01),
    )


class FakeAdapter:
    platform = "instagram"

    def __init__(self, items):
        self.items = items

    def list_content_items(self):
        return self.items

    def list_comment_threads(self, external_content_id):
        return []

    def post_reply(self, thread_external_id, text):
        raise NotImplementedError

    def update_reply(self, comment_external_id, text):
        raise NotImplementedError

    def delete_reply(self, comment_external_id):
        raise NotImplementedError


def _make_account(external_id: str) -> PlatformAccount:
    db = SessionLocal()
    try:
        account = db.scalar(select(PlatformAccount).where(PlatformAccount.platform == "instagram", PlatformAccount.external_account_id == external_id))
        if account is None:
            account = PlatformAccount(platform="instagram", external_account_id=external_id, display_name="ig-test", access_token_encrypted="x")
            db.add(account)
            db.commit()
            db.refresh(account)
        return account
    finally:
        db.close()


def test_report_is_none_when_no_publications_exist():
    # A platform key no other test ever writes Publication rows for — the shared
    # test DB persists across the whole module run (conftest.py resets it once,
    # not per test), so "facebook"/"instagram" themselves aren't reliably empty.
    db = SessionLocal()
    try:
        assert get_platform_intelligence_report(db, "never_synced_platform", now=NOW) is None
    finally:
        db.close()


def test_report_builds_with_enough_publications():
    account = _make_account("intel-a")
    adapter = FakeAdapter([_item("m1", 5000, 10), _item("m2", 1000, 5), _item("m3", 300, 1)])
    db = SessionLocal()
    try:
        sync_platform_content(db, account, adapter)
        report = get_platform_intelligence_report(db, "instagram", now=NOW)
        assert report is not None
        assert isinstance(report["winning_videos"], list)
        assert isinstance(report["topics"], list)
        # Honestly omitted rather than fabricated — no generic follower-history snapshot yet.
        assert report["daily_brief"]["subscribers_gained_24h"] is None
    finally:
        db.close()


def test_video_history_returns_none_for_unknown_video():
    db = SessionLocal()
    try:
        assert get_platform_video_history(db, "instagram", "does-not-exist", now=NOW) is None
    finally:
        db.close()


def test_video_history_buckets_snapshots_for_known_video():
    account = _make_account("intel-b")
    adapter = FakeAdapter([_item("m4", 2000, 8)])
    db = SessionLocal()
    try:
        sync_platform_content(db, account, adapter)
        history = get_platform_video_history(db, "instagram", "m4", now=NOW)
        assert history is not None
        assert "points" in history
        assert len(history["points"]) >= 1
    finally:
        db.close()
