from __future__ import annotations

from .conftest import register


def test_register_login_and_session(client):
    account = register(client, "Ada")
    me = client.get("/api/auth/me", headers=account["headers"])
    assert me.status_code == 200
    body = me.json()
    assert body["user"]["email"] == account["email"]
    assert body["workspaces"][0]["role"] == "owner"
    assert body["active_workspace_id"] == account["workspace_id"]

    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401

    login = client.post(
        "/api/auth/login", json={"email": account["email"], "password": account["password"]}
    )
    assert login.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_duplicate_email_and_bad_password(client):
    account = register(client, "Grace")
    duplicate = client.post(
        "/api/auth/register",
        json={"email": account["email"], "password": "OtherPass123", "name": "Dup"},
    )
    assert duplicate.status_code == 409
    wrong = client.post(
        "/api/auth/login", json={"email": account["email"], "password": "WrongPass123"}
    )
    assert wrong.status_code == 401
    weak = client.post(
        "/api/auth/register",
        json={"email": "weak@example.com", "password": "12345678", "name": "Weak"},
    )
    assert weak.status_code == 422


def test_profile_and_password_change(client):
    account = register(client, "Linus")
    updated = client.patch("/api/auth/profile", json={"name": "Linus T"}, headers=account["headers"])
    assert updated.status_code == 200
    assert updated.json()["name"] == "Linus T"

    changed = client.post(
        "/api/auth/password",
        json={"current_password": account["password"], "new_password": "NewStrongPass456"},
        headers=account["headers"],
    )
    assert changed.status_code == 204
    client.post("/api/auth/logout")
    old = client.post(
        "/api/auth/login", json={"email": account["email"], "password": account["password"]}
    )
    assert old.status_code == 401
    new = client.post(
        "/api/auth/login", json={"email": account["email"], "password": "NewStrongPass456"}
    )
    assert new.status_code == 200


def test_unauthenticated_requests_rejected(client):
    client.cookies.clear()
    assert client.get("/api/videos").status_code == 401
    assert client.get("/api/dashboard").status_code == 401
