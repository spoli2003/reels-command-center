from fastapi.testclient import TestClient
from app.main import app


def test_unified_content_flow():
    client = TestClient(app)
    video = client.post("/api/content/videos", json={"title": "Bank przestaje dostawać raty", "category": "Banki"})
    assert video.status_code == 201
    video_id = video.json()["id"]

    publication = client.post(
        f"/api/content/videos/{video_id}/publications",
        json={"platform": "youtube", "external_id": "abc123", "url": "https://youtube.test/abc123"},
    )
    assert publication.status_code == 201
    publication_id = publication.json()["id"]

    snapshot = client.post(
        f"/api/content/publications/{publication_id}/snapshots",
        json={"views": 1000, "likes": 50, "comments": 10, "shares": 4, "saves": 2},
    )
    assert snapshot.status_code == 201

    listed = client.get("/api/content/videos")
    assert listed.status_code == 200
    item = next(entry for entry in listed.json() if entry["id"] == video_id)
    assert item["total_views"] == 1000
    assert item["total_interactions"] == 66
