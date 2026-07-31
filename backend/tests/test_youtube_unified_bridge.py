"""Release 0.8.0 — youtube_unified_bridge.py (ADR-020). Verifies the dual-write
from YouTube's own dedicated sync/comment engine into the generic
ContentVideo/Publication/MetricSnapshot/ContentCommentThread/ContentComment
tables is purely additive (never touches YouTube's own tables) and never raises
even when it fails internally."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.comments import YoutubeComment, YoutubeCommentThread
from app.models.content import MetricSnapshot, Publication
from app.models.content_comments import ContentComment, ContentCommentThread
from app.models.integration import PlatformAccount, YoutubeChannel, YoutubeMetricSnapshot, YoutubeVideo
from app.services.youtube_unified_bridge import bridge_all_youtube_comments, bridge_all_youtube_videos


def _make_channel(external_id: str) -> tuple[PlatformAccount, YoutubeChannel]:
    db = SessionLocal()
    try:
        account = PlatformAccount(platform="youtube", external_account_id=external_id, display_name="Kanał bridge", access_token_encrypted="x")
        db.add(account)
        db.commit()
        db.refresh(account)
        channel = YoutubeChannel(account_id=account.id, youtube_channel_id=f"yt-{external_id}", title="Kanał bridge", uploads_playlist_id=f"uploads-{external_id}")
        db.add(channel)
        db.commit()
        db.refresh(channel)
        db.refresh(account)  # the channel commit above expires `account`'s attributes too
        return account, channel
    finally:
        db.close()


def test_bridge_creates_publication_and_snapshot_from_youtube_video():
    account, channel = _make_channel("bridge-a")
    db = SessionLocal()
    try:
        video = YoutubeVideo(
            channel_id=channel.id,
            youtube_video_id="bv-a1",
            title="Film mostkowany",
            description="Opis",
            published_at=datetime.now(timezone.utc) - timedelta(days=2),
            duration_seconds=45,
            thumbnail_url="https://example.test/thumb.jpg",
        )
        db.add(video)
        db.commit()
        db.refresh(video)
        snapshot = YoutubeMetricSnapshot(video_id=video.id, views=1000, likes=50, comments=5)
        db.add(snapshot)
        db.commit()

        bridge_all_youtube_videos(db, account, channel)

        publication = db.scalar(select(Publication).where(Publication.platform == "youtube", Publication.external_id == "bv-a1"))
        assert publication is not None
        assert publication.content_video.title == "Film mostkowany"
        bridged_snapshot = db.scalar(select(MetricSnapshot).where(MetricSnapshot.publication_id == publication.id))
        assert bridged_snapshot is not None
        assert bridged_snapshot.views == 1000
    finally:
        db.close()


def test_bridge_is_idempotent_and_does_not_duplicate_snapshots():
    account, channel = _make_channel("bridge-b")
    db = SessionLocal()
    try:
        video = YoutubeVideo(channel_id=channel.id, youtube_video_id="bv-b1", title="Film", description="", published_at=datetime.now(timezone.utc))
        db.add(video)
        db.commit()
        db.refresh(video)
        db.add(YoutubeMetricSnapshot(video_id=video.id, views=100, likes=1, comments=0))
        db.commit()

        bridge_all_youtube_videos(db, account, channel)
        bridge_all_youtube_videos(db, account, channel)  # same latest snapshot both times

        publication = db.scalar(select(Publication).where(Publication.platform == "youtube", Publication.external_id == "bv-b1"))
        snapshots = db.scalars(select(MetricSnapshot).where(MetricSnapshot.publication_id == publication.id)).all()
        assert len(snapshots) == 1
    finally:
        db.close()


def test_bridge_never_raises_on_internal_failure(monkeypatch):
    account, channel = _make_channel("bridge-c")
    db = SessionLocal()
    try:
        video = YoutubeVideo(channel_id=channel.id, youtube_video_id="bv-c1", title="Film", description="", published_at=datetime.now(timezone.utc))
        db.add(video)
        db.commit()

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated failure")

        monkeypatch.setattr("app.services.youtube_unified_bridge._bridge_one_video", _boom)
        bridge_all_youtube_videos(db, account, channel)  # must not raise despite _bridge_one_video blowing up
        assert db.scalar(select(Publication).where(Publication.platform == "youtube", Publication.external_id == "bv-c1")) is None
    finally:
        db.close()


def test_bridge_comments_creates_generic_thread_and_reply():
    account, channel = _make_channel("bridge-d")
    db = SessionLocal()
    try:
        video = YoutubeVideo(channel_id=channel.id, youtube_video_id="bv-d1", title="Film", description="", published_at=datetime.now(timezone.utc))
        db.add(video)
        db.commit()
        db.refresh(video)
        db.add(YoutubeMetricSnapshot(video_id=video.id, views=10, likes=0, comments=1))
        db.commit()
        bridge_all_youtube_videos(db, account, channel)

        now = datetime.now(timezone.utc)
        thread = YoutubeCommentThread(
            video_id=video.id,
            platform_thread_id="bridge-thread-d1",
            top_level_comment_id="bridge-comment-d1",
            author_channel_id="viewer-1",
            author_display_name="Widz",
            text_original="Pytanie",
            like_count=0,
            published_at=now,
            updated_at=now,
            total_reply_count=1,
            can_reply=True,
            imported_at=now,
            last_synced_at=now,
        )
        db.add(thread)
        db.commit()
        db.refresh(thread)
        reply = YoutubeComment(
            thread_id=thread.id,
            platform_comment_id="bridge-reply-d1",
            parent_comment_id="bridge-comment-d1",
            author_channel_id=channel.youtube_channel_id,
            author_display_name="Kanał bridge",
            text_original="Odpowiedź",
            like_count=0,
            published_at=now,
            updated_at=now,
            is_own_reply=True,
            imported_at=now,
            last_synced_at=now,
        )
        db.add(reply)
        db.commit()

        bridge_all_youtube_comments(db, account)

        bridged_thread = db.scalar(select(ContentCommentThread).where(ContentCommentThread.platform_thread_id == "bridge-thread-d1"))
        assert bridged_thread is not None
        assert bridged_thread.text_original == "Pytanie"
        bridged_reply = db.scalar(select(ContentComment).where(ContentComment.platform_comment_id == "bridge-reply-d1"))
        assert bridged_reply is not None
        assert bridged_reply.is_own_reply is True
    finally:
        db.close()


def test_bridge_comments_skips_thread_whose_video_is_not_bridged_yet():
    account, channel = _make_channel("bridge-e")
    db = SessionLocal()
    try:
        video = YoutubeVideo(channel_id=channel.id, youtube_video_id="bv-e1", title="Film niezmostkowany", description="", published_at=datetime.now(timezone.utc))
        db.add(video)
        db.commit()
        db.refresh(video)
        now = datetime.now(timezone.utc)
        thread = YoutubeCommentThread(
            video_id=video.id,
            platform_thread_id="thread-e1",
            top_level_comment_id="comment-e1",
            author_channel_id="viewer-1",
            author_display_name="Widz",
            text_original="Pytanie",
            like_count=0,
            published_at=now,
            updated_at=now,
            total_reply_count=0,
            can_reply=True,
            imported_at=now,
            last_synced_at=now,
        )
        db.add(thread)
        db.commit()

        # bridge_all_youtube_videos was never called for this video — must not raise.
        bridge_all_youtube_comments(db, account)

        bridged_thread = db.scalar(select(ContentCommentThread).where(ContentCommentThread.platform_thread_id == "thread-e1"))
        assert bridged_thread is None
    finally:
        db.close()
