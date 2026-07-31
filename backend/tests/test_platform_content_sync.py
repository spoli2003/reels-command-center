"""Release 0.8.0 — generic multi-platform content sync (ADR-020). Mirrors
tests/test_youtube.py's FakeYoutubeClient pattern but drives content_sync.py
through a fake PlatformAdapter, so Facebook/Instagram's sync engine gets the
same idempotency/dedup/fault-isolation coverage YouTube's has."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.content import MetricSnapshot, Publication
from app.models.integration import PlatformAccount, SyncRun
from app.services.content_sync import (
    ContentSyncAlreadyRunningError,
    get_publications_with_latest_snapshot,
    sync_platform_content,
)
from app.services.platforms.base import RawContentItem
from app.services.sync_recovery import INTERRUPTED_MESSAGE, recover_interrupted_sync_runs


def _item(external_id, title="Materiał testowy", views=1000, likes=50, comments=5, published_days_ago=3, followers_gained=None):
    return RawContentItem(
        external_id=external_id,
        title=title,
        description="Opis",
        url=f"https://example.test/{external_id}",
        published_at=datetime.now(timezone.utc) - timedelta(days=published_days_ago),
        thumbnail_url="https://example.test/thumb.jpg",
        duration_seconds=30,
        views=views,
        likes=likes,
        comments=comments,
        shares=2,
        saves=1,
        followers_gained=followers_gained,
    )


class FakeAdapter:
    platform = "facebook"

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


def _make_account(external_id: str, platform: str = "facebook") -> PlatformAccount:
    db = SessionLocal()
    try:
        account = db.scalar(select(PlatformAccount).where(PlatformAccount.platform == platform, PlatformAccount.external_account_id == external_id))
        if account is None:
            account = PlatformAccount(platform=platform, external_account_id=external_id, display_name="Strona testowa", access_token_encrypted="x")
            db.add(account)
            db.commit()
            db.refresh(account)
        return account
    finally:
        db.close()


def test_first_sync_imports_publications_and_snapshot():
    account = _make_account("page-a")
    adapter = FakeAdapter([_item("post-a1")])
    db = SessionLocal()
    try:
        run = sync_platform_content(db, account, adapter)
        assert run.status == "success"
        assert run.imported_items == 1
        assert run.videos_discovered == 1
        assert run.snapshots_created == 1

        publication = db.scalar(select(Publication).where(Publication.platform == "facebook", Publication.external_id == "post-a1"))
        assert publication is not None
        assert publication.content_video.title == "Materiał testowy"
        snapshot = db.scalar(select(MetricSnapshot).where(MetricSnapshot.publication_id == publication.id))
        assert snapshot.views == 1000
        assert snapshot.followers_gained is None
    finally:
        db.close()


def test_sync_persists_direct_per_content_audience_gain_when_adapter_provides_it():
    account = _make_account("page-audience-gain")
    adapter = FakeAdapter([_item("post-audience-gain", followers_gained=17)])
    db = SessionLocal()
    try:
        sync_platform_content(db, account, adapter)
        publication = db.scalar(
            select(Publication).where(Publication.platform == "facebook", Publication.external_id == "post-audience-gain")
        )
        snapshot = db.scalar(select(MetricSnapshot).where(MetricSnapshot.publication_id == publication.id))
        assert snapshot.followers_gained == 17
    finally:
        db.close()


def test_repeated_sync_upserts_publication_instead_of_duplicating():
    account = _make_account("page-b")
    adapter = FakeAdapter([_item("post-b1", title="Tytuł 1")])
    db = SessionLocal()
    try:
        sync_platform_content(db, account, adapter)
        adapter.items = [_item("post-b1", title="Zaktualizowany tytuł")]
        run2 = sync_platform_content(db, account, adapter)
        assert run2.imported_items == 0
        assert run2.videos_updated == 1

        publications = db.scalars(select(Publication).where(Publication.platform == "facebook", Publication.external_id == "post-b1")).all()
        assert len(publications) == 1
        assert publications[0].content_video.title == "Zaktualizowany tytuł"
    finally:
        db.close()


def test_sync_removes_locally_imported_content_now_excluded_by_adapter():
    account = _make_account("ig-cleanup", platform="instagram")
    adapter = FakeAdapter([_item("old-image")])
    adapter.platform = "instagram"
    db = SessionLocal()
    try:
        sync_platform_content(db, account, adapter)
        assert db.scalar(select(Publication).where(Publication.platform == "instagram", Publication.external_id == "old-image")) is not None

        adapter.items = [_item("new-reel")]
        adapter.excluded_content_ids = {"old-image"}
        sync_platform_content(db, account, adapter)

        assert db.scalar(select(Publication).where(Publication.platform == "instagram", Publication.external_id == "old-image")) is None
        assert db.scalar(select(Publication).where(Publication.platform == "instagram", Publication.external_id == "new-reel")) is not None
    finally:
        db.close()


def test_repeated_sync_reattaches_publication_after_account_reconnect():
    account = _make_account("page-reconnected")
    adapter = FakeAdapter([_item("post-reconnected")])
    db = SessionLocal()
    try:
        sync_platform_content(db, account, adapter)
        publication = db.scalar(
            select(Publication).where(
                Publication.platform == "facebook",
                Publication.external_id == "post-reconnected",
            )
        )
        publication.platform_account_id = None
        db.commit()

        sync_platform_content(db, account, adapter)
        db.refresh(publication)

        assert publication.platform_account_id == account.id
    finally:
        db.close()


def test_startup_recovery_marks_orphaned_running_syncs_failed():
    db = SessionLocal()
    try:
        content_run = SyncRun(platform="instagram", status="running")
        comment_run = SyncRun(platform="facebook_comments", status="running")
        db.add_all([content_run, comment_run])
        db.commit()

        assert recover_interrupted_sync_runs(db) == 2

        db.refresh(content_run)
        db.refresh(comment_run)
        assert content_run.status == "failed"
        assert comment_run.status == "failed"
        assert content_run.finished_at is not None
        assert comment_run.finished_at is not None
        assert content_run.error_message == INTERRUPTED_MESSAGE
        assert comment_run.error_message == INTERRUPTED_MESSAGE
    finally:
        db.close()


def test_sync_merges_legacy_alternate_publication_and_preserves_history():
    account = _make_account("page-facebook-wrapper-merge")
    wrapper_id = "page-facebook-wrapper-merge_post-1"
    canonical_id = "reel-video-1"
    db = SessionLocal()
    try:
        sync_platform_content(db, account, FakeAdapter([_item(wrapper_id, views=0, likes=7)]))
        wrapper = db.scalar(select(Publication).where(Publication.platform == "facebook", Publication.external_id == wrapper_id))
        wrapper_snapshot = db.scalar(select(MetricSnapshot).where(MetricSnapshot.publication_id == wrapper.id))
        wrapper_snapshot.impressions = 900
        db.commit()

        canonical_item = _item(canonical_id, views=2500, likes=4)
        canonical_item.alternate_external_ids = (wrapper_id,)
        run = sync_platform_content(db, account, FakeAdapter([canonical_item]))

        publications = db.scalars(
            select(Publication).where(Publication.platform == "facebook", Publication.external_id.in_([wrapper_id, canonical_id]))
        ).all()
        assert len(publications) == 1
        assert publications[0].external_id == canonical_id
        snapshots = db.scalars(select(MetricSnapshot).where(MetricSnapshot.publication_id == publications[0].id)).all()
        assert len(snapshots) == 1
        assert max(snapshot.views for snapshot in snapshots) == 2500
        assert max(snapshot.likes for snapshot in snapshots) == 7
        assert max(snapshot.impressions or 0 for snapshot in snapshots) == 900
        assert run.videos_discovered == 1
    finally:
        db.close()


def test_snapshot_dedup_within_interval_window():
    account = _make_account("page-c")
    adapter = FakeAdapter([_item("post-c1", views=1000)])
    db = SessionLocal()
    try:
        sync_platform_content(db, account, adapter)
        adapter.items = [_item("post-c1", views=2000)]
        run2 = sync_platform_content(db, account, adapter)
        assert run2.snapshots_created == 0
        assert run2.snapshots_deduplicated == 1

        publication = db.scalar(select(Publication).where(Publication.platform == "facebook", Publication.external_id == "post-c1"))
        snapshots = db.scalars(select(MetricSnapshot).where(MetricSnapshot.publication_id == publication.id)).all()
        assert len(snapshots) == 1
        assert snapshots[0].views == 1000  # second sync's snapshot was deduplicated away, not applied
    finally:
        db.close()


def test_one_failing_item_does_not_abort_the_whole_sync():
    account = _make_account("page-d")

    class PartiallyBrokenAdapter(FakeAdapter):
        def list_content_items(self):
            good = _item("post-d1")
            broken = _item("post-d2")
            broken.external_id = None  # will blow up the upsert (platform/external_id lookup requires a string)
            return [good, broken]

    adapter = PartiallyBrokenAdapter([])
    db = SessionLocal()
    try:
        run = sync_platform_content(db, account, adapter)
        assert run.status == "partial"
        assert run.videos_failed == 1
        assert run.imported_items == 1
        publication = db.scalar(select(Publication).where(Publication.platform == "facebook", Publication.external_id == "post-d1"))
        assert publication is not None
    finally:
        db.close()


def test_overlapping_sync_is_rejected():
    account = _make_account("page-e")
    db = SessionLocal()
    try:
        stuck_run = SyncRun(platform="facebook", status="running")
        db.add(stuck_run)
        db.commit()
        try:
            with pytest.raises(ContentSyncAlreadyRunningError):
                sync_platform_content(db, account, FakeAdapter([]))
        finally:
            db.delete(db.get(SyncRun, stuck_run.id))
            db.commit()
    finally:
        db.close()


def test_get_publications_with_latest_snapshot_filters_by_platform():
    account_fb = _make_account("page-f", platform="facebook")
    account_ig = _make_account("acct-f", platform="instagram")
    db = SessionLocal()
    try:
        sync_platform_content(db, account_fb, FakeAdapter([_item("post-f1")]))
        ig_adapter = FakeAdapter([_item("media-f1")])
        ig_adapter.platform = "instagram"
        sync_platform_content(db, account_ig, ig_adapter)

        fb_rows = get_publications_with_latest_snapshot(db, "facebook")
        assert any(pub.external_id == "post-f1" for pub, _snap in fb_rows)
        assert all(pub.platform == "facebook" for pub, _snap in fb_rows)

        all_rows = get_publications_with_latest_snapshot(db, None)
        assert len(all_rows) >= len(fb_rows)
    finally:
        db.close()
