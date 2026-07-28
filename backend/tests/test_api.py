import os

os.environ["DATABASE_URL"] = "sqlite:///./test-rcc.db"

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_list_reel():
    created = client.post(
        "/api/reels",
        json={"title": "Testowa rolka", "category": "Banki", "hook": "Od dziś bank..."},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["title"] == "Testowa rolka"

    listed = client.get("/api/reels")
    assert listed.status_code == 200
    assert any(item["id"] == body["id"] for item in listed.json())
