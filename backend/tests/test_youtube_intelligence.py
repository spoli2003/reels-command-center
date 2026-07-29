from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.integration import PlatformAccount, YoutubeChannel, YoutubeChannelSnapshot, YoutubeMetricSnapshot, YoutubeVideo

client = TestClient(app)


@pytest.fixture(scope="module")
def seeded_channel():
    db = SessionLocal()
    try:
        account = PlatformAccount(
            platform="youtube",
            external_account_id="intel-channel",
            display_name="Kanał testowy",
            access_token_encrypted="x",
        )
        db.add(account)
        db.commit()
        db.refresh(account)

        now = datetime.now(timezone.utc)
        channel = YoutubeChannel(
            account_id=account.id,
            youtube_channel_id="intel-channel",
            title="Kanał testowy",
            uploads_playlist_id="uploads-intel",
            subscriber_count=1000,
            view_count=50000,
            video_count=6,
            synced_at=now,
        )
        db.add(channel)
        db.commit()
        db.refresh(channel)

        db.add_all(
            [
                YoutubeChannelSnapshot(channel_id=channel.id, captured_at=now - timedelta(days=2), subscriber_count=980, view_count=49000, video_count=6),
                YoutubeChannelSnapshot(channel_id=channel.id, captured_at=now, subscriber_count=1000, view_count=50000, video_count=6),
            ]
        )

        titles = [
            "Wypadek przy pracy w kopalni",
            "Jak zgłosić wypadek w kopalni",
            "Urlop wypoczynkowy zasady",
            "Renta wypadkowa krok po kroku",
            "ZUS i emerytura co warto wiedzieć",
            "Najnowszy odcinek o mobbingu",
        ]
        video_ids = []
        for index, title in enumerate(titles):
            video = YoutubeVideo(
                channel_id=channel.id,
                youtube_video_id=f"intel-video-{index}",
                title=title,
                description="",
                published_at=now - timedelta(days=40 - index * 5),
            )
            db.add(video)
            db.commit()
            db.refresh(video)
            video_ids.append(video.youtube_video_id)
            db.add(YoutubeMetricSnapshot(video_id=video.id, captured_at=now - timedelta(days=2), views=100 * (index + 1), likes=5, comments=1))
            db.add(YoutubeMetricSnapshot(video_id=video.id, captured_at=now, views=150 * (index + 1), likes=8, comments=2))
        db.commit()
        return video_ids
    finally:
        db.close()


def test_intelligence_endpoint_returns_full_structure(seeded_channel):
    response = client.get("/api/integrations/youtube/analytics/intelligence")
    assert response.status_code == 200
    body = response.json()
    for key in [
        "daily_brief",
        "winning_videos",
        "attention_videos",
        "too_new_count",
        "topics",
        "publishing",
        "follow_up_opportunities",
        "title_patterns",
        "content_recommendations",
    ]:
        assert key in body


def test_intelligence_daily_brief_has_real_numbers(seeded_channel):
    response = client.get("/api/integrations/youtube/analytics/intelligence")
    brief = response.json()["daily_brief"]
    assert brief["views_gained_24h"] is not None
    assert brief["views_gained_24h"] > 0


def test_intelligence_topics_cluster_shared_keywords(seeded_channel):
    response = client.get("/api/integrations/youtube/analytics/intelligence")
    keywords = {topic["keyword"] for topic in response.json()["topics"]}
    assert "wypadek" in keywords or "kopalni" in keywords


def test_intelligence_winning_videos_have_confidence_and_support(seeded_channel):
    response = client.get("/api/integrations/youtube/analytics/intelligence")
    winning = response.json()["winning_videos"]
    assert len(winning) > 0
    for rec in winning:
        assert rec["confidence"] in ("low", "medium", "high")
        assert rec["supporting_videos"]


def test_intelligence_recommendations_never_use_forbidden_absolute_wording(seeded_channel):
    response = client.get("/api/integrations/youtube/analytics/intelligence")
    body = response.json()
    forbidden = ["zawsze", "gwarantuje", "na pewno", "always", "guarantees"]
    all_categories = (
        body["winning_videos"]
        + body["attention_videos"]
        + body["follow_up_opportunities"]
        + body["title_patterns"]
        + body["content_recommendations"]
    )
    for rec in all_categories:
        lowered = rec["explanation"].lower()
        for word in forbidden:
            assert word not in lowered
