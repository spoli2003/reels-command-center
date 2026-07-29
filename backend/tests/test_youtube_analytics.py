from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.integration import PlatformAccount, YoutubeChannel, YoutubeMetricSnapshot, YoutubeVideo

client = TestClient(app)


@pytest.fixture(scope="module")
def seeded_videos():
    db = SessionLocal()
    try:
        account = PlatformAccount(
            platform="youtube",
            external_account_id="analytics-channel",
            display_name="Kanał analityczny",
            access_token_encrypted="x",
        )
        db.add(account)
        db.commit()
        db.refresh(account)

        channel = YoutubeChannel(
            account_id=account.id,
            youtube_channel_id="analytics-channel",
            title="Kanał analityczny",
            uploads_playlist_id="uploads-analytics",
            subscriber_count=500,
            view_count=10000,
            video_count=2,
            synced_at=datetime.now(timezone.utc),
        )
        db.add(channel)
        db.commit()
        db.refresh(channel)

        now = datetime.now(timezone.utc)
        video_a = YoutubeVideo(
            channel_id=channel.id,
            youtube_video_id="analytics-video-a",
            title="Najlepszy film",
            description="Opis A",
            published_at=now - timedelta(days=10),
            duration_seconds=45,
            is_short_candidate=True,
        )
        video_b = YoutubeVideo(
            channel_id=channel.id,
            youtube_video_id="analytics-video-b",
            title="Drugi film",
            description="Opis B",
            published_at=now - timedelta(days=2),
            duration_seconds=300,
            is_short_candidate=False,
        )
        db.add_all([video_a, video_b])
        db.commit()
        db.refresh(video_a)
        db.refresh(video_b)

        older = now - timedelta(days=1)
        db.add_all(
            [
                YoutubeMetricSnapshot(video_id=video_a.id, captured_at=older, views=500, likes=50, comments=5),
                YoutubeMetricSnapshot(video_id=video_a.id, captured_at=now, views=1000, likes=100, comments=10),
                YoutubeMetricSnapshot(video_id=video_b.id, captured_at=now, views=200, likes=10, comments=1),
            ]
        )
        db.commit()
        return video_a.youtube_video_id, video_b.youtube_video_id
    finally:
        db.close()


def test_summary_uses_latest_snapshot_per_video(seeded_videos):
    video_a_id, _ = seeded_videos
    response = client.get("/api/integrations/youtube/analytics/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["total_videos"] >= 2
    assert body["total_views"] >= 1200
    assert body["subscriber_count"] == 500

    detail = client.get(f"/api/integrations/youtube/videos/{video_a_id}")
    assert detail.status_code == 200
    assert detail.json()["views"] == 1000
    assert detail.json()["like_ratio"] == 10.0


def test_summary_and_status_agree_on_channel_identity(seeded_videos):
    """Release 0.6.1 bugfix: /analytics/summary and /status must derive channel
    identity/subscriber count from the exact same lookup (get_channel), never two
    independently-written queries that could silently diverge."""
    summary = client.get("/api/integrations/youtube/analytics/summary").json()
    status = client.get("/api/integrations/youtube/status").json()
    assert summary["channel_title"] == status["channel_title"]
    assert "last_synced_at" not in summary
    assert status["last_synced_at"] is not None


def test_top_and_scatter_and_history(seeded_videos):
    top_by_views = client.get("/api/integrations/youtube/analytics/top", params={"metric": "views", "limit": 5})
    assert top_by_views.status_code == 200
    titles = [item["title"] for item in top_by_views.json()]
    assert titles.index("Najlepszy film") < titles.index("Drugi film")

    scatter = client.get("/api/integrations/youtube/analytics/scatter")
    assert scatter.status_code == 200
    assert len(scatter.json()) >= 2

    history = client.get("/api/integrations/youtube/videos/analytics-video-a/history")
    assert history.status_code == 200
    history_body = history.json()
    assert len(history_body["points"]) == 2
    assert history_body["granularity"] == "daily"
    assert isinstance(history_body["buckets"], list)
    assert "insufficient" in history_body

    missing = client.get("/api/integrations/youtube/videos/does-not-exist")
    assert missing.status_code == 404


def test_timeseries_and_upload_frequency(seeded_videos):
    timeseries = client.get("/api/integrations/youtube/analytics/timeseries", params={"metric": "views"})
    assert timeseries.status_code == 200
    assert len(timeseries.json()) >= 1

    frequency = client.get("/api/integrations/youtube/analytics/upload-frequency", params={"interval": "month"})
    assert frequency.status_code == 200
    assert sum(item["count"] for item in frequency.json()) >= 2


def test_videos_list_and_detail_expose_structured_metadata(seeded_videos):
    """Sprint 5 / Part 8: /videos and /videos/{id} must agree on the same
    deterministic metadata for the same video, computed by the same function."""
    video_a_id, _ = seeded_videos

    videos_response = client.get("/api/integrations/youtube/videos")
    assert videos_response.status_code == 200
    rows = {row["youtube_video_id"]: row for row in videos_response.json()}
    assert video_a_id in rows
    row = rows[video_a_id]
    for field in [
        "views_per_day",
        "engagement_rate",
        "trend",
        "performance_score",
        "performance_label",
        "engagement_category",
        "growth_category",
        "topic_keywords",
    ]:
        assert field in row

    detail_response = client.get(f"/api/integrations/youtube/videos/{video_a_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()

    # Same video, same underlying computation — list and detail must agree.
    assert detail["performance_score"] == row["performance_score"]
    assert detail["performance_label"] == row["performance_label"]
    assert detail["trend"] == row["trend"]
    assert detail["growth_category"] == row["growth_category"]
    assert isinstance(detail["topic_keywords"], list)

    # Sprint 6 / Parts 7 & 12 — historical growth metadata present on both.
    for field in ["velocity", "acceleration", "views_gained_24h", "views_gained_7d", "views_gained_30d", "snapshot_count"]:
        assert field in row
        assert field in detail


def test_channel_history_endpoint(seeded_videos):
    """Sprint 6 / Part 10."""
    response = client.get("/api/integrations/youtube/channel/history")
    assert response.status_code == 200
    body = response.json()
    assert body["granularity"] in ("daily", "weekly", "monthly")
    assert isinstance(body["buckets"], list)
    assert "insufficient" in body


def test_data_quality_endpoint(seeded_videos):
    """Sprint 6 / Part 13."""
    response = client.get("/api/integrations/youtube/data-quality")
    assert response.status_code == 200
    body = response.json()
    assert body["videos_checked"] >= 2
    assert body["snapshots_checked"] >= 3
    assert "is_clean" in body
