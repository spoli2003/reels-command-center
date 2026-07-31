"""Release 0.8.0 — generic Community Engine reuse for Facebook/Instagram
(ADR-020). Mirrors tests/test_youtube_comments.py's fake-client pattern but
drives the generic content_comment_sync/content_comments_query/
content_comment_actions trio through a fake PlatformAdapter, over the generic
ContentCommentThread/ContentComment tables."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.content_comments import ContentComment, ContentCommentThread
from app.models.integration import PlatformAccount, SyncRun
from app.services import content_comment_actions as actions
from app.services.content_comment_sync import ContentCommentSyncAlreadyRunningError, sync_platform_comments
from app.services.content_comments_query import build_inbox_rows, build_inbox_summary, filter_and_sort_rows
from app.services.content_sync import sync_platform_content
from app.services.platforms.base import RawComment, RawCommentThread, RawContentItem

NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)


def _content_item(external_id, published_days_ago=3):
    return RawContentItem(
        external_id=external_id,
        title=f"Materiał {external_id}",
        description="",
        url=f"https://example.test/{external_id}",
        published_at=NOW - timedelta(days=published_days_ago),
        thumbnail_url=None,
        duration_seconds=None,
        views=100,
        likes=5,
        comments=1,
    )


def _content_item_without_comments(external_id):
    item = _content_item(external_id)
    item.comments = 0
    return item


def _comment(external_id, text, is_own=False, author_external_id="viewer-1", published_at=NOW, parent_external_id=None):
    return RawComment(
        external_id=external_id,
        parent_external_id=parent_external_id,
        author_external_id=author_external_id,
        author_display_name="Widz Testowy" if not is_own else "Strona Testowa",
        author_avatar_url=None,
        text=text,
        like_count=0,
        published_at=published_at,
        is_own=is_own,
    )


def _thread(thread_id, top_level, replies=None, can_reply=True):
    replies = replies or []
    return RawCommentThread(
        external_id=thread_id,
        top_level=top_level,
        total_reply_count=len(replies),
        can_reply=can_reply,
        replies=replies,
    )


class FakeCommentAdapter:
    platform = "facebook"

    def __init__(self, threads_by_content=None):
        self.threads_by_content = threads_by_content or {}
        self.posted: list[tuple[str, str]] = []
        self.updated: list[tuple[str, str]] = []
        self.deleted: list[str] = []
        self._counter = 0

    def list_content_items(self):
        return [_content_item(cid) for cid in self.threads_by_content]

    def list_comment_threads(self, external_content_id):
        return self.threads_by_content.get(external_content_id, [])

    def post_reply(self, thread_external_id, text):
        self._counter += 1
        self.posted.append((thread_external_id, text))
        return _comment(f"reply-new-{thread_external_id}-{self._counter}", text, is_own=True, author_external_id="page-own", parent_external_id=thread_external_id)

    def update_reply(self, comment_external_id, text):
        self.updated.append((comment_external_id, text))
        return _comment(comment_external_id, text, is_own=True, author_external_id="page-own")

    def delete_reply(self, comment_external_id):
        self.deleted.append(comment_external_id)


def _make_account(external_id: str) -> PlatformAccount:
    db = SessionLocal()
    try:
        account = db.scalar(select(PlatformAccount).where(PlatformAccount.platform == "facebook", PlatformAccount.external_account_id == external_id))
        if account is None:
            account = PlatformAccount(platform="facebook", external_account_id=external_id, display_name="page-own", access_token_encrypted="x")
            db.add(account)
            db.commit()
            db.refresh(account)
        return account
    finally:
        db.close()


def _sync_content_and_comments(db, account, adapter):
    sync_platform_content(db, account, adapter)
    return sync_platform_comments(db, account, adapter)


def test_import_first_thread_with_reply():
    account = _make_account("page-cm-a")
    top = _comment("comment-a1", "Świetny post!")
    reply = _comment("reply-a1", "Dzięki!", is_own=True, author_external_id="page-own", parent_external_id="comment-a1")
    adapter = FakeCommentAdapter({"post-cm-a1": [_thread("comment-a1", top, replies=[reply])]})

    db = SessionLocal()
    try:
        run = _sync_content_and_comments(db, account, adapter)
        assert run.status == "success"
        assert run.threads_discovered == 1
        assert run.comments_imported == 1
        assert run.replies_imported == 1

        thread = db.scalar(select(ContentCommentThread).where(ContentCommentThread.platform_thread_id == "comment-a1"))
        assert thread is not None
        assert thread.text_original == "Świetny post!"
        replies = db.scalars(select(ContentComment).where(ContentComment.thread_id == thread.id)).all()
        assert len(replies) == 1
        assert replies[0].is_own_reply is True
    finally:
        db.close()


def test_repeated_sync_upserts_instead_of_duplicating():
    account = _make_account("page-cm-b")
    top = _comment("comment-b1", "Pierwszy tekst")
    adapter = FakeCommentAdapter({"post-cm-b1": [_thread("comment-b1", top)]})
    db = SessionLocal()
    try:
        _sync_content_and_comments(db, account, adapter)
        top2 = _comment("comment-b1", "Zaktualizowany tekst")
        adapter.threads_by_content["post-cm-b1"] = [_thread("comment-b1", top2)]
        run2 = _sync_content_and_comments(db, account, adapter)
        assert run2.comments_imported == 0

        threads = db.scalars(select(ContentCommentThread).where(ContentCommentThread.platform_thread_id == "comment-b1")).all()
        assert len(threads) == 1
        assert threads[0].text_original == "Zaktualizowany tekst"
    finally:
        db.close()


def test_comment_sync_skips_remote_call_when_latest_snapshot_reports_zero_comments():
    account = _make_account("page-cm-zero")

    class ZeroCommentAdapter(FakeCommentAdapter):
        def __init__(self):
            super().__init__()
            self.requested = []

        def list_content_items(self):
            return [_content_item_without_comments("post-cm-zero")]

        def list_comment_threads(self, external_content_id):
            self.requested.append(external_content_id)
            return []

    adapter = ZeroCommentAdapter()
    db = SessionLocal()
    try:
        sync_platform_content(db, account, adapter)
        run = sync_platform_comments(db, account, adapter)

        assert run.status == "success"
        assert run.videos_discovered == 1
        assert adapter.requested == []
    finally:
        db.close()


def test_thread_omitted_from_later_sync_is_retained_locally():
    account = _make_account("page-cm-c")
    top = _comment("comment-c1", "Zniknie z listy API")
    adapter = FakeCommentAdapter({"post-cm-c1": [_thread("comment-c1", top)]})
    db = SessionLocal()
    try:
        _sync_content_and_comments(db, account, adapter)
        adapter.threads_by_content["post-cm-c1"] = []
        _sync_content_and_comments(db, account, adapter)
        thread = db.scalar(select(ContentCommentThread).where(ContentCommentThread.platform_thread_id == "comment-c1"))
        assert thread is not None
    finally:
        db.close()


def test_overlapping_comment_sync_is_rejected():
    account = _make_account("page-cm-d")
    db = SessionLocal()
    try:
        stuck_run = SyncRun(platform="facebook_comments", status="running")
        db.add(stuck_run)
        db.commit()
        try:
            with pytest.raises(ContentCommentSyncAlreadyRunningError):
                sync_platform_comments(db, account, FakeCommentAdapter({}))
        finally:
            db.delete(db.get(SyncRun, stuck_run.id))
            db.commit()
    finally:
        db.close()


def test_conversation_state_and_priority_via_build_inbox_rows():
    account = _make_account("page-cm-e")
    own = "page-own"
    resolved_top = _comment("comment-e1", "Pytanie", published_at=NOW - timedelta(hours=2))
    resolved_reply = _comment("reply-e1", "Odpowiedź", is_own=True, author_external_id=own, published_at=NOW - timedelta(hours=1), parent_external_id="comment-e1")
    new_top = _comment("comment-e2", "Nikt nie odpowiedział", published_at=NOW - timedelta(hours=1))
    own_top = _comment("comment-e3", "Pełny materiał tutaj", is_own=True, author_external_id=own, published_at=NOW)
    adapter = FakeCommentAdapter(
        {
            "post-cm-e1": [_thread("comment-e1", resolved_top, replies=[resolved_reply])],
            "post-cm-e2": [_thread("comment-e2", new_top)],
            "post-cm-e3": [_thread("comment-e3", own_top)],
        }
    )
    db = SessionLocal()
    try:
        _sync_content_and_comments(db, account, adapter)
        rows = build_inbox_rows(db, account.id, own_external_id=own, now=NOW)
        by_thread = {r["thread"].platform_thread_id: r for r in rows}

        assert by_thread["comment-e1"]["conversation_state"].value == "resolved"
        assert by_thread["comment-e1"]["priority_score"] == 0.0
        assert by_thread["comment-e2"]["conversation_state"].value == "new"
        assert by_thread["comment-e2"]["priority_score"] > 0.0
        assert by_thread["comment-e3"]["is_own_thread"] is True

        summary = build_inbox_summary(rows, now=NOW)
        assert summary["resolved_count"] == 1
        assert summary["awaiting_reply_count"] == 1
        assert summary["total_visible"] == 2
        assert summary["own_threads_count"] == 1

        resolved_only = filter_and_sort_rows(rows, quick="resolved", now=NOW)
        assert {r["thread"].platform_thread_id for r in resolved_only} == {"comment-e1"}
        viewer_threads = filter_and_sort_rows(rows, quick="all", now=NOW)
        assert {r["thread"].platform_thread_id for r in viewer_threads} == {"comment-e1", "comment-e2"}
        own_threads = filter_and_sort_rows(rows, quick="mine", now=NOW)
        assert {r["thread"].platform_thread_id for r in own_threads} == {"comment-e3"}
    finally:
        db.close()


def test_post_reply_creates_own_comment_and_bumps_reply_count():
    account = _make_account("page-cm-f")
    top = _comment("comment-f1", "Pytanie do strony")
    adapter = FakeCommentAdapter({"post-cm-f1": [_thread("comment-f1", top)]})
    db = SessionLocal()
    try:
        _sync_content_and_comments(db, account, adapter)
        reply = actions.post_reply(db, account, adapter, "comment-f1", "Dziękujemy za komentarz.")
        assert reply.is_own_reply is True
        assert adapter.posted == [("comment-f1", "Dziękujemy za komentarz.")]

        thread = db.scalar(select(ContentCommentThread).where(ContentCommentThread.platform_thread_id == "comment-f1"))
        assert thread.total_reply_count == 1
    finally:
        db.close()


def test_post_reply_rejects_thread_from_another_account():
    account_a = _make_account("page-cm-g1")
    account_b = _make_account("page-cm-g2")
    top = _comment("comment-g1", "Pytanie")
    adapter = FakeCommentAdapter({"post-cm-g1": [_thread("comment-g1", top)]})
    db = SessionLocal()
    try:
        _sync_content_and_comments(db, account_a, adapter)
        with pytest.raises(actions.ContentCommentActionError):
            actions.post_reply(db, account_b, adapter, "comment-g1", "Nie powinno się udać.")
    finally:
        db.close()


def test_edit_and_delete_require_own_reply():
    account = _make_account("page-cm-h")
    top = _comment("comment-h1", "Pytanie")
    adapter = FakeCommentAdapter({"post-cm-h1": [_thread("comment-h1", top)]})
    db = SessionLocal()
    try:
        _sync_content_and_comments(db, account, adapter)

        # Editing/deleting the viewer's own top-level comment (not RCC's reply) must be rejected.
        with pytest.raises(actions.ContentCommentActionError):
            actions.get_own_reply(db, account, "comment-h1")

        reply = actions.post_reply(db, account, adapter, "comment-h1", "Odpowiedź.")
        edited = actions.edit_reply(db, account, adapter, reply.platform_comment_id, "Zaktualizowana odpowiedź.")
        assert edited.text_original == "Zaktualizowana odpowiedź."
        assert adapter.updated == [(reply.platform_comment_id, "Zaktualizowana odpowiedź.")]

        actions.delete_reply(db, account, adapter, reply.platform_comment_id)
        assert adapter.deleted == [reply.platform_comment_id]
        remaining = db.scalar(select(ContentComment).where(ContentComment.platform_comment_id == reply.platform_comment_id))
        assert remaining is None

        thread = db.scalar(select(ContentCommentThread).where(ContentCommentThread.platform_thread_id == "comment-h1"))
        assert thread.total_reply_count == 0
    finally:
        db.close()


def test_empty_reply_text_is_rejected():
    account = _make_account("page-cm-i")
    top = _comment("comment-i1", "Pytanie")
    adapter = FakeCommentAdapter({"post-cm-i1": [_thread("comment-i1", top)]})
    db = SessionLocal()
    try:
        _sync_content_and_comments(db, account, adapter)
        with pytest.raises(actions.ContentCommentActionError):
            actions.post_reply(db, account, adapter, "comment-i1", "   ")
    finally:
        db.close()
