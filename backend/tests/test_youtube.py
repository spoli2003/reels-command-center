import os
from datetime import datetime, timezone
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test-rcc.db"
os.environ["TOKEN_ENCRYPTION_KEY"] = "test-secret"
os.environ["GOOGLE_CLIENT_SECRETS_FILE"] = "tests/fixtures/google_client_secret.json"

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.integration import PlatformAccount, YoutubeMetricSnapshot, YoutubeVideo
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
