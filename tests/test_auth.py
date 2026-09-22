def test_login_returns_token(client):
    response = client.post("/auth/login", data={"username": "admin", "password": "correct-horse"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_rejects_wrong_password(client):
    response = client.post("/auth/login", data={"username": "admin", "password": "nope"})
    assert response.status_code == 401


def test_login_rejects_unknown_user(client):
    response = client.post("/auth/login", data={"username": "someone", "password": "correct-horse"})
    assert response.status_code == 401


def test_me_returns_current_admin(client, auth_headers):
    response = client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"username": "admin"}


def test_admin_routes_require_token(client):
    assert client.get("/admin/videos").status_code == 401
    assert client.patch("/admin/videos/1", json={"title": "x"}).status_code == 401
    assert client.delete("/admin/videos/1").status_code == 401
    assert client.post("/admin/videos/1/restore").status_code == 401


def test_admin_routes_reject_bad_token(client):
    response = client.get("/admin/videos", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


def test_password_change_in_env_is_applied(db_session, monkeypatch):
    from catalog_service import auth, config

    monkeypatch.setattr(config, "ADMIN_PASSWORD", "new-password")
    auth.ensure_admin_user(db_session)
    assert auth.authenticate(db_session, "admin", "new-password") is not None
    assert auth.authenticate(db_session, "admin", "correct-horse") is None
