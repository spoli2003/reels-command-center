import os
from datetime import datetime, timezone
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test-rcc.db"
os.environ["TOKEN_ENCRYPTION_KEY"] = "test-secret"
os.environ["GOOGLE_CLIENT_SECRETS_FILE"] = "tests/fixtures/google_client_secret.json"

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.integration import PlatformAccount, SyncRun, YoutubeChannelSnapshot, YoutubeMetricSnapshot, YoutubeVideo
from app.services.token_crypto import decrypt_token, encrypt_token
from app.services.youtube_sync import sync_youtube


class FakeYoutubeClient:
    def get_my_channel(self):
        return {
            "id": "channel-1",
            "snippet": {"title": "Kanał testowy", "thumbnails": {"high": {"url": "https://example.test/channel.jpg"}}},
            "contentDetails": {"relatedPlaylists": {"uploads": "uploads-1"}},
            "statistics": {"subscriberCount": "123", "viewCount": "9000", "videoCount": "1"},
        }

    def list_upload_video_ids(self, playlist_id, max_items=100):
        assert playlist_id == "uploads-1"
        return ["video-1"]

    def get_videos(self, video_ids):
        return [{
            "id": "video-1",
            "snippet": {"title": "Testowy Short", "description": "Opis", "publishedAt": "2026-07-28T10:00:00Z", "thumbnails": {"high": {"url": "https://example.test/video.jpg"}}},
            "contentDetails": {"duration": "PT59S"},
            "statistics": {"viewCount": "1000", "likeCount": "50", "commentCount": "7"},
        }]


def test_token_roundtrip():
    encrypted = encrypt_token("sekretny-token", "test-secret")
    assert encrypted != "sekretny-token"
    assert decrypt_token(encrypted, "test-secret") == "sekretny-token"


def test_youtube_sync_persists_channel_video_and_snapshot():
    db = SessionLocal()
    try:
        account = db.scalar(select(PlatformAccount).where(PlatformAccount.external_account_id == "channel-1"))
        if account is None:
            account = PlatformAccount(platform="youtube", external_account_id="channel-1", display_name="Kanał testowy", access_token_encrypted="x")
            db.add(account)
            db.commit()
            db.refresh(account)
        channel, imported = sync_youtube(db, account, FakeYoutubeClient())
        assert channel.title == "Kanał testowy"
        assert imported in (0, 1)
        video = db.scalar(select(YoutubeVideo).where(YoutubeVideo.youtube_video_id == "video-1"))
        assert video is not None
        assert video.duration_seconds == 59
        assert video.is_short_candidate is True
        snapshot = db.scalar(select(YoutubeMetricSnapshot).where(YoutubeMetricSnapshot.video_id == video.id).order_by(YoutubeMetricSnapshot.id.desc()))
        assert snapshot is not None
        assert snapshot.views == 1000
    finally:
        db.close()


class FakeYoutubeClientChannel2:
    """A distinct channel/video id set so this test's first-ever sync isn't
    affected by the snapshot dedup window (Sprint 6 / Part 3) from another test
    that already synced "channel-1"/"video-1" moments earlier."""

    def get_my_channel(self):
        return {
            "id": "channel-2",
            "snippet": {"title": "Kanał testowy 2", "thumbnails": {"high": {"url": "https://example.test/channel2.jpg"}}},
            "contentDetails": {"relatedPlaylists": {"uploads": "uploads-2"}},
            "statistics": {"subscriberCount": "456", "viewCount": "8000", "videoCount": "1"},
        }

    def list_upload_video_ids(self, playlist_id, max_items=100):
        assert playlist_id == "uploads-2"
        return ["video-2"]

    def get_videos(self, video_ids):
        return [{
            "id": "video-2",
            "snippet": {"title": "Testowy Short 2", "description": "Opis", "publishedAt": "2026-07-28T10:00:00Z", "thumbnails": {"high": {"url": "https://example.test/video2.jpg"}}},
            "contentDetails": {"duration": "PT59S"},
            "statistics": {"viewCount": "2000", "likeCount": "80", "commentCount": "9"},
        }]


def test_sync_run_records_visible_effects_and_channel_snapshot():
    """Guards against the 'sync appears to have no visible effect' bug: every
    successful run must leave an auditable trail (SyncRun counts + a channel snapshot)."""
    db = SessionLocal()
    try:
        account = db.scalar(select(PlatformAccount).where(PlatformAccount.external_account_id == "channel-2"))
        if account is None:
            account = PlatformAccount(platform="youtube", external_account_id="channel-2", display_name="Kanał testowy 2", access_token_encrypted="x")
            db.add(account)
            db.commit()
            db.refresh(account)

        channel, _ = sync_youtube(db, account, FakeYoutubeClientChannel2())

        run = db.scalar(select(SyncRun).where(SyncRun.platform == "youtube").order_by(SyncRun.id.desc()))
        assert run is not None
        assert run.status == "success"
        assert run.videos_discovered >= 1
        assert run.snapshots_created >= 1
        assert run.videos_discovered == run.snapshots_created
        assert run.finished_at is not None
        assert run.finished_at >= run.started_at

        channel_snapshot = db.scalar(
            select(YoutubeChannelSnapshot).where(YoutubeChannelSnapshot.channel_id == channel.id).order_by(YoutubeChannelSnapshot.id.desc())
        )
        assert channel_snapshot is not None
        assert channel_snapshot.subscriber_count == channel.subscriber_count
    finally:
        db.close()


def test_repeated_sync_deduplicates_snapshots_instead_of_creating_duplicates():
    """Sprint 6 / Part 3: an immediate repeat sync of the same account must not
    create a second near-identical snapshot for the same video/channel."""
    db = SessionLocal()
    try:
        account = PlatformAccount(platform="youtube", external_account_id="channel-dedup", display_name="Kanał dedup", access_token_encrypted="x")
        db.add(account)
        db.commit()
        db.refresh(account)

        class FakeClient:
            def get_my_channel(self):
                return {
                    "id": "channel-dedup",
                    "snippet": {"title": "Kanał dedup"},
                    "contentDetails": {"relatedPlaylists": {"uploads": "uploads-dedup"}},
                    "statistics": {"subscriberCount": "10", "viewCount": "100", "videoCount": "1"},
                }

            def list_upload_video_ids(self, playlist_id, max_items=100):
                return ["video-dedup"]

            def get_videos(self, video_ids):
                return [{
                    "id": "video-dedup",
                    "snippet": {"title": "Dedup Test", "description": "", "publishedAt": "2026-07-28T10:00:00Z"},
                    "contentDetails": {"duration": "PT30S"},
                    "statistics": {"viewCount": "500", "likeCount": "5", "commentCount": "1"},
                }]

        sync_youtube(db, account, FakeClient())
        video = db.scalar(select(YoutubeVideo).where(YoutubeVideo.youtube_video_id == "video-dedup"))
        first_snapshot_count = len(db.scalars(select(YoutubeMetricSnapshot).where(YoutubeMetricSnapshot.video_id == video.id)).all())
        assert first_snapshot_count == 1

        # Immediate repeat — must be recognized as a duplicate, not a second data point.
        sync_youtube(db, account, FakeClient())
        second_snapshot_count = len(db.scalars(select(YoutubeMetricSnapshot).where(YoutubeMetricSnapshot.video_id == video.id)).all())
        assert second_snapshot_count == 1

        second_run = db.scalar(select(SyncRun).where(SyncRun.platform == "youtube").order_by(SyncRun.id.desc()))
        assert second_run.snapshots_created == 0
        assert second_run.snapshots_deduplicated >= 1
        assert second_run.status == "success"
    finally:
        db.close()


def test_overlapping_sync_is_rejected_while_one_is_running():
    """Sprint 6 / Part 5: a sync requested while another is still 'running' for the
    same platform must be rejected, not silently start a second concurrent run."""
    from app.services.youtube_sync import SyncAlreadyRunningError

    db = SessionLocal()
    try:
        account = PlatformAccount(platform="youtube", external_account_id="channel-overlap", display_name="Kanał overlap", access_token_encrypted="x")
        db.add(account)
        db.commit()
        db.refresh(account)

        stuck_run = SyncRun(platform="youtube", status="running")
        db.add(stuck_run)
        db.commit()

        try:
            sync_youtube(db, account, FakeYoutubeClient())
            assert False, "expected SyncAlreadyRunningError"
        except SyncAlreadyRunningError:
            pass
        finally:
            # Don't leak a permanently-"running" row into later tests/queries.
            db.delete(db.get(SyncRun, stuck_run.id))
            db.commit()
    finally:
        db.close()


def test_stale_running_sync_is_reclaimed_after_restart():
    """Sprint 6 / Part 5: a 'running' SyncRun stuck past STALE_RUN_MINUTES is
    treated as an orphan from a crash/restart, not a real in-flight sync — a new
    sync must be allowed to proceed and the stale row marked failed."""
    from datetime import timedelta

    from app.services.youtube_sync import STALE_RUN_MINUTES

    db = SessionLocal()
    try:
        account = PlatformAccount(platform="youtube", external_account_id="channel-stale", display_name="Kanał stale", access_token_encrypted="x")
        db.add(account)
        db.commit()
        db.refresh(account)

        stale_run = SyncRun(
            platform="youtube",
            status="running",
            started_at=datetime.now(timezone.utc) - timedelta(minutes=STALE_RUN_MINUTES + 5),
        )
        db.add(stale_run)
        db.commit()
        stale_run_id = stale_run.id

        class FakeClient:
            def get_my_channel(self):
                return {
                    "id": "channel-stale",
                    "snippet": {"title": "Kanał stale"},
                    "contentDetails": {"relatedPlaylists": {"uploads": "uploads-stale"}},
                    "statistics": {"subscriberCount": "1", "viewCount": "1", "videoCount": "0"},
                }

            def list_upload_video_ids(self, playlist_id, max_items=100):
                return []

            def get_videos(self, video_ids):
                return []

        sync_youtube(db, account, FakeClient())

        reclaimed = db.get(SyncRun, stale_run_id)
        assert reclaimed.status == "failed"
    finally:
        db.close()
