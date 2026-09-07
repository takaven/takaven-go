from fastapi.testclient import TestClient


def test_protected_page_redirects_to_login(client: TestClient):
    response = client.get("/truth", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_invalid_password_is_rejected(client: TestClient):
    response = client.post("/login", data={"password": "wrong-password"})
    assert response.status_code == 401
    assert "not accepted" in response.text
    assert "takaven_session" not in response.cookies


def test_valid_password_creates_secure_session_boundary(client: TestClient):
    response = client.post(
        "/login", data={"password": "stage-one-test-password"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/truth"
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert client.get("/truth").status_code == 200
