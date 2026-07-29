"""Release 0.7.0 — Community Inbox. Mocks the YouTube API deterministically via a
fake client (same pattern as tests/test_youtube.py's FakeYoutubeClient) — no live
API calls in automated tests, per Part 14."""

from datetime import datetime, timedelta, timezone

import pytest
from googleapiclient.errors import HttpError
from sqlalchemy import select

from app.db.session import SessionLocal
from app.integrations.youtube.oauth import has_comments_scope
from app.models.comments import YoutubeComment, YoutubeCommentThread
from app.models.integration import PlatformAccount, SyncRun, YoutubeChannel, YoutubeVideo
from app.services.comment_intelligence import ConversationState, comment_priority_score, determine_conversation_state, is_likely_question
from app.services.youtube_comment_actions import CommentActionError, delete_reply, edit_reply, post_reply
from app.services.youtube_comment_sync import CommentSyncAlreadyRunningError, sync_youtube_comments
from app.services.youtube_comments_query import build_inbox_rows, filter_and_sort_rows

NOW = "2026-07-29T12:00:00Z"


class FakeResp:
    def __init__(self, status):
        self.status = status
        self.reason = ""


def _comments_disabled_error() -> HttpError:
    content = b'{"error": {"errors": [{"reason": "commentsDisabled", "message": "disabled"}], "code": 403, "message": "disabled"}}'
    return HttpError(FakeResp(403), content, uri="https://example.test")


def _thread_payload(thread_id, comment_id, text, published_at=NOW, total_reply_count=0, inline_replies=None, author_channel_id="viewer-1"):
    return {
        "id": thread_id,
        "snippet": {
            "topLevelComment": {
                "id": comment_id,
                "snippet": {
                    "authorChannelId": {"value": author_channel_id},
                    "authorDisplayName": "Widz Testowy",
                    "authorProfileImageUrl": "https://example.test/a.png",
                    "textOriginal": text,
                    "likeCount": 3,
                    "publishedAt": published_at,
                    "updatedAt": published_at,
                },
            },
            "totalReplyCount": total_reply_count,
            "canReply": True,
        },
        "replies": {"comments": inline_replies or []},
    }


def _reply_payload(reply_id, parent_id, text, published_at=NOW, author_channel_id="channel-comments-1"):
    return {
        "id": reply_id,
        "snippet": {
            "parentId": parent_id,
            "authorChannelId": {"value": author_channel_id},
            "authorDisplayName": "Kanał Testowy",
            "textOriginal": text,
            "likeCount": 0,
            "publishedAt": published_at,
            "updatedAt": published_at,
        },
    }


class FakeCommentClient:
    def __init__(self, threads_by_video=None, replies_by_parent=None, comments_disabled_videos=None, pages_by_video=None):
        self.threads_by_video = threads_by_video or {}
        self.replies_by_parent = replies_by_parent or {}
        self.comments_disabled_videos = comments_disabled_videos or set()
        self.pages_by_video = pages_by_video or {}  # video_id -> list of pages (each a list of raw threads)
        self.inserted: list[tuple[str, str]] = []
        self.updated: list[tuple[str, str]] = []
        self.deleted: list[str] = []

    def list_comment_threads_page(self, video_id, page_token=None):
        if video_id in self.comments_disabled_videos:
            raise _comments_disabled_error()
        if video_id in self.pages_by_video:
            pages = self.pages_by_video[video_id]
            index = int(page_token) if page_token else 0
            items = pages[index]
            next_token = str(index + 1) if index + 1 < len(pages) else None
            return {"items": items, "nextPageToken": next_token}
        return {"items": self.threads_by_video.get(video_id, [])}

    def list_replies_page(self, parent_id, page_token=None):
        return {"items": self.replies_by_parent.get(parent_id, [])}

    def insert_reply(self, parent_id, text):
        # Include parent_id so generated IDs stay globally unique across tests —
        # the test DB persists for the whole module run (reset once, not per-test).
        comment_id = f"reply-new-{parent_id}-{len(self.inserted) + 1}"
        self.inserted.append((parent_id, text))
        return _reply_payload(comment_id, parent_id, text)

    def update_comment(self, comment_id, text):
        self.updated.append((comment_id, text))
        return {"id": comment_id, "snippet": {"textOriginal": text, "publishedAt": NOW, "updatedAt": "2026-07-29T13:00:00Z"}}

    def delete_comment(self, comment_id):
        self.deleted.append(comment_id)


def _make_channel(external_id: str, title: str) -> tuple[PlatformAccount, YoutubeChannel]:
    db = SessionLocal()
    try:
        account = PlatformAccount(platform="youtube", external_account_id=external_id, display_name=title, access_token_encrypted="x")
        db.add(account)
        db.commit()
        db.refresh(account)
        channel = YoutubeChannel(
            account_id=account.id,
            youtube_channel_id=f"yt-{external_id}",
            title=title,
            uploads_playlist_id=f"uploads-{external_id}",
        )
        db.add(channel)
        db.commit()
        db.refresh(channel)
        return account, channel
    finally:
        db.close()


def _make_video(channel_id: int, youtube_video_id: str, published_days_ago: int = 5) -> YoutubeVideo:
    db = SessionLocal()
    try:
        video = YoutubeVideo(
            channel_id=channel_id,
            youtube_video_id=youtube_video_id,
            title=f"Film {youtube_video_id}",
            description="",
            published_at=datetime.now(timezone.utc) - timedelta(days=published_days_ago),
        )
        db.add(video)
        db.commit()
        db.refresh(video)
        return video
    finally:
        db.close()


def test_import_first_comment_thread():
    _, channel = _make_channel("comments-a", "Kanał A")
    video = _make_video(channel.id, "video-a1")
    client = FakeCommentClient(threads_by_video={"video-a1": [_thread_payload("thread-1", "comment-1", "Świetny film!")]})

    db = SessionLocal()
    try:
        run = sync_youtube_comments(db, channel, client, mode="full")
        assert run.status == "success"
        assert run.threads_discovered == 1
        assert run.comments_imported == 1

        thread = db.scalar(select(YoutubeCommentThread).where(YoutubeCommentThread.platform_thread_id == "thread-1"))
        assert thread is not None
        assert thread.text_original == "Świetny film!"
        assert thread.video_id == video.id
    finally:
        db.close()


def test_import_all_replies_including_backfill_beyond_inline():
    _, channel = _make_channel("comments-b", "Kanał B")
    _make_video(channel.id, "video-b1")
    inline = [_reply_payload("reply-1", "comment-b1", "Dzięki za komentarz!")]
    extra = [_reply_payload("reply-2", "comment-b1", "I jeszcze jedno.")]
    client = FakeCommentClient(
        threads_by_video={"video-b1": [_thread_payload("thread-b1", "comment-b1", "Pytanie?", total_reply_count=2, inline_replies=inline)]},
        replies_by_parent={"comment-b1": inline + extra},
    )

    db = SessionLocal()
    try:
        run = sync_youtube_comments(db, channel, client, mode="full")
        assert run.replies_imported == 2
        thread = db.scalar(select(YoutubeCommentThread).where(YoutubeCommentThread.platform_thread_id == "thread-b1"))
        replies = db.scalars(select(YoutubeComment).where(YoutubeComment.thread_id == thread.id)).all()
        assert {r.platform_comment_id for r in replies} == {"reply-1", "reply-2"}
    finally:
        db.close()


def test_repeated_sync_upserts_instead_of_duplicating():
    _, channel = _make_channel("comments-c", "Kanał C")
    video = _make_video(channel.id, "video-c1")
    client = FakeCommentClient(threads_by_video={"video-c1": [_thread_payload("thread-c1", "comment-c1", "Pierwszy tekst")]})

    db = SessionLocal()
    try:
        sync_youtube_comments(db, channel, client, mode="full")
        first_count = len(db.scalars(select(YoutubeCommentThread).where(YoutubeCommentThread.video_id == video.id)).all())

        client.threads_by_video["video-c1"][0]["snippet"]["topLevelComment"]["snippet"]["textOriginal"] = "Zaktualizowany tekst"
        run2 = sync_youtube_comments(db, channel, client, mode="full")
        second_count = len(db.scalars(select(YoutubeCommentThread).where(YoutubeCommentThread.video_id == video.id)).all())

        assert first_count == second_count == 1
        assert run2.comments_imported == 0  # upsert, not a new import
        thread = db.scalar(select(YoutubeCommentThread).where(YoutubeCommentThread.platform_thread_id == "thread-c1"))
        assert thread.text_original == "Zaktualizowany tekst"
    finally:
        db.close()


def test_pagination_across_multiple_thread_pages():
    _, channel = _make_channel("comments-d", "Kanał D")
    _make_video(channel.id, "video-d1")
    page0 = [_thread_payload("thread-d1", "comment-d1", "Pierwsza strona")]
    page1 = [_thread_payload("thread-d2", "comment-d2", "Druga strona")]
    client = FakeCommentClient(pages_by_video={"video-d1": [page0, page1]})

    db = SessionLocal()
    try:
        run = sync_youtube_comments(db, channel, client, mode="full")
        assert run.threads_discovered == 2
        ids = {t.platform_thread_id for t in db.scalars(select(YoutubeCommentThread)).all()}
        assert {"thread-d1", "thread-d2"} <= ids
    finally:
        db.close()


def test_comments_disabled_video_is_skipped_not_failed():
    _, channel = _make_channel("comments-e", "Kanał E")
    _make_video(channel.id, "video-e1")
    client = FakeCommentClient(comments_disabled_videos={"video-e1"})

    db = SessionLocal()
    try:
        run = sync_youtube_comments(db, channel, client, mode="full")
        assert run.status == "success"
        assert run.videos_failed == 0
        assert run.threads_discovered == 0
    finally:
        db.close()


def test_deleted_or_omitted_comment_is_retained_locally():
    """A thread no longer returned by a later sync must NOT be removed locally —
    only insertion/update happens, never deletion-on-absence."""
    _, channel = _make_channel("comments-f", "Kanał F")
    _make_video(channel.id, "video-f1")
    client = FakeCommentClient(threads_by_video={"video-f1": [_thread_payload("thread-f1", "comment-f1", "Będzie usunięty z listy API")]})

    db = SessionLocal()
    try:
        sync_youtube_comments(db, channel, client, mode="full")
        client.threads_by_video["video-f1"] = []  # API "forgets" the thread
        sync_youtube_comments(db, channel, client, mode="full")
        thread = db.scalar(select(YoutubeCommentThread).where(YoutubeCommentThread.platform_thread_id == "thread-f1"))
        assert thread is not None
    finally:
        db.close()


def test_likely_question_classification():
    assert is_likely_question("Czy to zadziała w moim przypadku?")
    assert is_likely_question("Jak długo trwa taka sprawa")
    assert is_likely_question("Nie rozumiem, o co chodzi")
    assert not is_likely_question("Świetny film, dzięki!")
    assert not is_likely_question("")


def test_conversation_state_matrix():
    """Release 0.7.1 / Parts 1 & 9 — the exact four scenarios from the release
    brief. Conversation state must be derived from the LAST message in the full
    thread, never the top-level comment alone."""
    _, channel = _make_channel("comments-g", "Kanał G")
    _make_video(channel.id, "video-g1")
    own = channel.youtube_channel_id  # "yt-comments-g"
    t0, t1, t2, t3 = (
        "2026-07-29T10:00:00Z",
        "2026-07-29T11:00:00Z",
        "2026-07-29T12:00:00Z",
        "2026-07-29T13:00:00Z",
    )

    client = FakeCommentClient(
        threads_by_video={
            "video-g1": [
                # User -> Channel -> Resolved
                _thread_payload(
                    "thread-resolved",
                    "comment-resolved",
                    "Pytanie o film",
                    published_at=t0,
                    total_reply_count=1,
                    inline_replies=[_reply_payload("reply-resolved-1", "comment-resolved", "Dzięki!", published_at=t1, author_channel_id=own)],
                ),
                # User -> Channel -> User -> Waiting
                _thread_payload(
                    "thread-waiting",
                    "comment-waiting",
                    "Pierwsza wiadomość",
                    published_at=t0,
                    total_reply_count=2,
                    inline_replies=[
                        _reply_payload("reply-waiting-1", "comment-waiting", "Odpowiedź kanału", published_at=t1, author_channel_id=own),
                        _reply_payload("reply-waiting-2", "comment-waiting", "Kolejne pytanie widza", published_at=t2, author_channel_id="viewer-1"),
                    ],
                ),
                # User only -> New
                _thread_payload("thread-new", "comment-new", "Nikt jeszcze nie odpowiedział"),
                # User -> Channel -> User -> Channel -> Resolved
                _thread_payload(
                    "thread-resolved-again",
                    "comment-resolved-again",
                    "Długa wymiana",
                    published_at=t0,
                    total_reply_count=3,
                    inline_replies=[
                        _reply_payload("reply-ra-1", "comment-resolved-again", "Pierwsza odpowiedź", published_at=t1, author_channel_id=own),
                        _reply_payload("reply-ra-2", "comment-resolved-again", "Dopytanie widza", published_at=t2, author_channel_id="viewer-1"),
                        _reply_payload("reply-ra-3", "comment-resolved-again", "Druga odpowiedź", published_at=t3, author_channel_id=own),
                    ],
                ),
            ]
        }
    )
    db = SessionLocal()
    try:
        sync_youtube_comments(db, channel, client, mode="full")
        rows = build_inbox_rows(db, channel.id, own)
        by_thread = {r["thread"].platform_thread_id: r for r in rows}

        assert by_thread["thread-resolved"]["conversation_state"] == ConversationState.RESOLVED
        assert by_thread["thread-waiting"]["conversation_state"] == ConversationState.WAITING
        assert by_thread["thread-new"]["conversation_state"] == ConversationState.NEW
        assert by_thread["thread-resolved-again"]["conversation_state"] == ConversationState.RESOLVED

        resolved = filter_and_sort_rows(rows, quick="resolved")
        assert {r["thread"].platform_thread_id for r in resolved} == {"thread-resolved", "thread-resolved-again"}
        waiting = filter_and_sort_rows(rows, quick="waiting")
        assert {r["thread"].platform_thread_id for r in waiting} == {"thread-waiting"}
        new = filter_and_sort_rows(rows, quick="new")
        assert {r["thread"].platform_thread_id for r in new} == {"thread-new"}

        # "unanswered" convenience alias = new + waiting, never resolved/closed.
        unanswered = filter_and_sort_rows(rows, quick="unanswered")
        assert {r["thread"].platform_thread_id for r in unanswered} == {"thread-waiting", "thread-new"}

        # Resolved conversations are never prioritized (Part 2).
        assert by_thread["thread-resolved"]["priority_score"] == 0.0
        assert by_thread["thread-resolved-again"]["priority_score"] == 0.0
        assert by_thread["thread-waiting"]["priority_score"] > 0.0
        assert by_thread["thread-new"]["priority_score"] > 0.0
    finally:
        db.close()


def test_self_authored_top_level_comment_is_resolved_not_new():
    """Bug found via live verification (Release 0.7.1 / Part 8): a channel's own
    pinned top-level comment (a common creator practice, e.g. linking the full
    video) has zero replies, but must NOT be flagged "New / needs reply" — the
    channel already has the last (and only) word."""
    _, channel = _make_channel("comments-p", "Kanał P")
    _make_video(channel.id, "video-p1")
    own = channel.youtube_channel_id
    client = FakeCommentClient(
        threads_by_video={"video-p1": [_thread_payload("thread-pinned", "comment-pinned", "Pełny materiał tutaj: link", author_channel_id=own)]}
    )
    db = SessionLocal()
    try:
        sync_youtube_comments(db, channel, client, mode="full")
        rows = build_inbox_rows(db, channel.id, own)
        row = next(r for r in rows if r["thread"].platform_thread_id == "thread-pinned")
        assert row["conversation_state"] == ConversationState.RESOLVED
        assert row["priority_score"] == 0.0
    finally:
        db.close()


def _thread_payload_with_likes(thread_id, comment_id, text, like_count):
    payload = _thread_payload(thread_id, comment_id, text)
    payload["snippet"]["topLevelComment"]["snippet"]["likeCount"] = like_count
    return payload


def test_like_sorting_and_highly_liked_highlighting():
    """Release 0.7.1 / Part 3 & 9 — sorting by like count, and the percentile-based
    "highly liked" highlight (never a fake Like button — see docs/DECISIONS.md)."""
    _, channel = _make_channel("comments-n", "Kanał N")
    _make_video(channel.id, "video-n1")
    client = FakeCommentClient(
        threads_by_video={
            "video-n1": [
                _thread_payload_with_likes("thread-low", "comment-n1", "Mało polubień", 1),
                _thread_payload_with_likes("thread-mid", "comment-n2", "Średnio polubień", 5),
                _thread_payload_with_likes("thread-high", "comment-n3", "Bardzo polubiony komentarz", 500),
            ]
        }
    )
    db = SessionLocal()
    try:
        sync_youtube_comments(db, channel, client, mode="full")
        rows = build_inbox_rows(db, channel.id, channel.youtube_channel_id)

        most_liked = filter_and_sort_rows(rows, sort="most_liked")
        assert [r["thread"].platform_thread_id for r in most_liked] == ["thread-high", "thread-mid", "thread-low"]

        by_thread = {r["thread"].platform_thread_id: r for r in rows}
        assert by_thread["thread-high"]["is_highly_liked"] is True
        assert by_thread["thread-low"]["is_highly_liked"] is False

        highly_liked = filter_and_sort_rows(rows, quick="highly_liked")
        assert {r["thread"].platform_thread_id for r in highly_liked} == {"thread-high"}
    finally:
        db.close()


def test_viewer_rating_captured_read_only():
    """Part 3 — viewerRating is captured from the API as read-only data, never a
    fake Like button or a value RCC invents itself."""
    _, channel = _make_channel("comments-o", "Kanał O")
    _make_video(channel.id, "video-o1")
    payload = _thread_payload("thread-o1", "comment-o1", "Komentarz polubiony przez kanał")
    payload["snippet"]["topLevelComment"]["snippet"]["viewerRating"] = "like"
    client = FakeCommentClient(threads_by_video={"video-o1": [payload]})

    db = SessionLocal()
    try:
        sync_youtube_comments(db, channel, client, mode="full")
        thread = db.scalar(select(YoutubeCommentThread).where(YoutubeCommentThread.platform_thread_id == "thread-o1"))
        assert thread.viewer_rating == "like"
    finally:
        db.close()


def test_reply_publishing_success():
    _, channel = _make_channel("comments-h", "Kanał H")
    _make_video(channel.id, "video-h1")
    client = FakeCommentClient(threads_by_video={"video-h1": [_thread_payload("thread-h1", "comment-h1", "Pytanie?")]})
    db = SessionLocal()
    try:
        sync_youtube_comments(db, channel, client, mode="full")
        reply = post_reply(db, channel, client, "thread-h1", "Dziękuję za komentarz.")
        assert reply.is_own_reply is True
        assert reply.text_original == "Dziękuję za komentarz."
        assert client.inserted == [("comment-h1", "Dziękuję za komentarz.")]

        thread = db.scalar(select(YoutubeCommentThread).where(YoutubeCommentThread.platform_thread_id == "thread-h1"))
        assert thread.total_reply_count == 1
    finally:
        db.close()


def test_reply_publishing_failure_does_not_create_local_row():
    _, channel = _make_channel("comments-i", "Kanał I")
    _make_video(channel.id, "video-i1")
    client = FakeCommentClient(threads_by_video={"video-i1": [_thread_payload("thread-i1", "comment-i1", "Pytanie?")]})

    def _raise(parent_id, text):
        raise _comments_disabled_error()

    db = SessionLocal()
    try:
        sync_youtube_comments(db, channel, client, mode="full")
        thread = db.scalar(select(YoutubeCommentThread).where(YoutubeCommentThread.platform_thread_id == "thread-i1"))
        client.insert_reply = _raise
        with pytest.raises(HttpError):
            post_reply(db, channel, client, "thread-i1", "To się nie uda.")
        replies = db.scalars(select(YoutubeComment).where(YoutubeComment.thread_id == thread.id)).all()
        assert len(replies) == 0
    finally:
        db.close()


def test_cannot_reply_to_thread_from_another_channel():
    _, channel_a = _make_channel("comments-j1", "Kanał J1")
    _make_video(channel_a.id, "video-j1")
    _, channel_b = _make_channel("comments-j2", "Kanał J2")
    client = FakeCommentClient(threads_by_video={"video-j1": [_thread_payload("thread-j1", "comment-j1", "Pytanie?")]})

    db = SessionLocal()
    try:
        sync_youtube_comments(db, channel_a, client, mode="full")
        with pytest.raises(CommentActionError):
            post_reply(db, channel_b, client, "thread-j1", "Nie powinno się udać.")
    finally:
        db.close()


def test_own_reply_edit_and_delete_authorization():
    _, channel = _make_channel("comments-k", "Kanał K")
    _make_video(channel.id, "video-k1")
    client = FakeCommentClient(threads_by_video={"video-k1": [_thread_payload("thread-k1", "comment-k1", "Pytanie?")]})
    db = SessionLocal()
    try:
        sync_youtube_comments(db, channel, client, mode="full")
        reply = post_reply(db, channel, client, "thread-k1", "Odpowiedź.")

        # Editing/deleting a viewer's own comment (not RCC's reply) must be rejected.
        with pytest.raises(CommentActionError):
            edit_reply(db, channel, client, "comment-k1", "Próba edycji cudzego komentarza")
        with pytest.raises(CommentActionError):
            delete_reply(db, channel, client, "comment-k1")

        edited = edit_reply(db, channel, client, reply.platform_comment_id, "Zaktualizowana odpowiedź.")
        assert edited.text_original == "Zaktualizowana odpowiedź."
        assert client.updated == [(reply.platform_comment_id, "Zaktualizowana odpowiedź.")]

        delete_reply(db, channel, client, reply.platform_comment_id)
        assert client.deleted == [reply.platform_comment_id]
        remaining = db.scalar(select(YoutubeComment).where(YoutubeComment.platform_comment_id == reply.platform_comment_id))
        assert remaining is None
    finally:
        db.close()


def test_overlapping_comment_sync_is_rejected():
    _, channel = _make_channel("comments-l", "Kanał L")
    _make_video(channel.id, "video-l1")
    client = FakeCommentClient(threads_by_video={"video-l1": []})

    db = SessionLocal()
    try:
        stuck_run = SyncRun(platform="youtube_comments", status="running")
        db.add(stuck_run)
        db.commit()
        try:
            with pytest.raises(CommentSyncAlreadyRunningError):
                sync_youtube_comments(db, channel, client, mode="full")
        finally:
            db.delete(db.get(SyncRun, stuck_run.id))
            db.commit()
    finally:
        db.close()


def test_has_comments_scope():
    assert has_comments_scope("https://www.googleapis.com/auth/youtube.force-ssl https://www.googleapis.com/auth/yt-analytics.readonly")
    assert not has_comments_scope("https://www.googleapis.com/auth/youtube.readonly")
    assert not has_comments_scope("")
    assert not has_comments_scope(None)


def test_comment_priority_score_ranks_unanswered_questions_highest():
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    waiting_question = comment_priority_score(
        state=ConversationState.WAITING, is_question=True, last_message_at=now, like_count=5, reply_count=0, now=now
    )
    waiting_statement = comment_priority_score(
        state=ConversationState.WAITING, is_question=False, last_message_at=now, like_count=5, reply_count=0, now=now
    )
    new_question = comment_priority_score(
        state=ConversationState.NEW, is_question=True, last_message_at=now, like_count=5, reply_count=0, now=now
    )
    resolved_question = comment_priority_score(
        state=ConversationState.RESOLVED, is_question=True, last_message_at=now, like_count=5, reply_count=0, now=now
    )
    closed_question = comment_priority_score(
        state=ConversationState.CLOSED, is_question=True, last_message_at=now, like_count=5, reply_count=0, now=now
    )
    assert waiting_question > waiting_statement
    assert new_question > 0.0
    assert resolved_question == 0.0
    assert closed_question == 0.0


def test_determine_conversation_state_priority_order():
    # Moderated/closed wins even if the channel replied.
    assert determine_conversation_state(has_own_reply=True, last_message_is_own=True, is_moderated=True) == ConversationState.CLOSED
    # No reply ever from the channel -> New, regardless of who's "last" (there's only one message).
    assert determine_conversation_state(has_own_reply=False, last_message_is_own=False, is_moderated=False) == ConversationState.NEW
    # Channel replied and has the last word -> Resolved.
    assert determine_conversation_state(has_own_reply=True, last_message_is_own=True, is_moderated=False) == ConversationState.RESOLVED
    # Channel replied before, but the viewer spoke again since -> Waiting.
    assert determine_conversation_state(has_own_reply=True, last_message_is_own=False, is_moderated=False) == ConversationState.WAITING
