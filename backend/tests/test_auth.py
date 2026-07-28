from fastapi.testclient import TestClient
from app.main import app

def test_register_login_me(monkeypatch):
    client = TestClient(app)
    response = client.post('/api/auth/register', json={'email':'test@example.com','full_name':'Test User','password':'very-secure-password'})
    assert response.status_code in (201, 409)
    response = client.post('/api/auth/login', json={'email':'test@example.com','password':'very-secure-password'})
    assert response.status_code == 200
    assert client.get('/api/auth/me').status_code == 200
    assert client.post('/api/auth/logout').status_code == 204
