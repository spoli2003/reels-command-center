from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete

import app.services.global_sync as global_sync_module
from app.db.session import SessionLocal
from app.main import app
from app.models.integration import PlatformAccount, SyncRun
from app.schemas.synchronization import GlobalSyncPlatformResult

client = TestClient(app)


def _clean() -> None:
    db = SessionLocal()
    try:
        db.execute(delete(SyncRun).where(SyncRun.platform.in_(["sync-test", "facebook_comments"])))
        db.execute(delete(PlatformAccount).where(PlatformAccount.external_account_id.like("sync-test-%")))
        db.commit()
    finally:
        db.close()


def test_synchronization_overview_has_all_supported_platforms_and_history():
    _clean()
    db = SessionLocal()
    try:
        db.add(
            SyncRun(
                platform="facebook_comments",
                status="success",
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                videos_discovered=10,
                videos_updated=4,
                comments_imported=7,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/api/synchronization?history_limit=10")
    assert response.status_code == 200
    body = response.json()
    assert {item["platform"] for item in body["platforms"]} == {"youtube", "facebook", "instagram"}
    comment_run = next(item for item in body["history"] if item["platform"] == "facebook" and item["kind"] == "comments")
    assert comment_run["comments_imported"] == 7
    assert comment_run["items_discovered"] == 10
    assert comment_run["items_processed"] == 4
    _clean()


def test_synchronization_overview_closes_orphaned_running_status():
    _clean()
    db = SessionLocal()
    try:
        db.add(
            SyncRun(
                platform="sync-test",
                status="running",
                started_at=datetime.now(timezone.utc) - timedelta(minutes=31),
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/api/synchronization?history_limit=100")
    assert response.status_code == 200
    stale_run = next(item for item in response.json()["history"] if item["platform"] == "sync-test")
    assert stale_run["status"] == "failed"
    assert "30 minut" in stale_run["error_message"]
    _clean()


def test_global_sync_skips_disconnected_platforms(monkeypatch):
    _clean()
    db = SessionLocal()
    try:
        db.execute(delete(PlatformAccount).where(PlatformAccount.platform.in_(["youtube", "facebook", "instagram"])))
        db.commit()
    finally:
        db.close()

    response = client.post("/api/synchronization/sync-all")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "skipped"
    assert [item["status"] for item in body["results"]] == ["skipped", "skipped", "skipped"]


def test_global_sync_isolates_one_platform_failure(monkeypatch):
    _clean()
    db = SessionLocal()
    try:
        for platform in ("youtube", "facebook"):
            db.add(
                PlatformAccount(
                    platform=platform,
                    external_account_id=f"sync-test-{platform}",
                    display_name=f"Test {platform}",
                    access_token_encrypted="test",
                )
            )
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(
        global_sync_module,
        "_sync_youtube",
        lambda *_args: GlobalSyncPlatformResult(platform="youtube", status="success", message="OK", imported_items=2),
    )

    def fail_meta(*_args):
        raise RuntimeError("Kontrolowany błąd Meta")

    monkeypatch.setattr(global_sync_module, "_sync_meta", fail_meta)
    response = client.post("/api/synchronization/sync-all")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    by_platform = {item["platform"]: item for item in body["results"]}
    assert by_platform["youtube"]["status"] == "success"
    assert by_platform["facebook"]["status"] == "failed"
    assert "RuntimeError" in by_platform["facebook"]["message"]
    assert by_platform["instagram"]["status"] == "skipped"
    _clean()
