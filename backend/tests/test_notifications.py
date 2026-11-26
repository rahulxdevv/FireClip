from __future__ import annotations

from app.database import SessionLocal
from app.models import Notification

from .conftest import register


def add_notification(workspace_id: str, user_id: str | None, title: str) -> str:
    with SessionLocal() as db:
        note = Notification(workspace_id=workspace_id, user_id=user_id, type="info", title=title)
        db.add(note)
        db.commit()
        return note.id


def test_notifications_combine_workspace_and_personal_entries(client, account):
    other = register(client, "Someone else")
    # Registering signs the second user in; restore the session under test.
    relogin = client.post(
        "/api/auth/login", json={"email": account["email"], "password": account["password"]}
    )
    assert relogin.status_code == 200, relogin.text

    workspace_note = add_notification(account["workspace_id"], None, "Workspace update")
    personal_note = add_notification(account["workspace_id"], account["user_id"], "Your render finished")
    add_notification(account["workspace_id"], other["user_id"], "Addressed to another user")
    add_notification(other["workspace_id"], other["user_id"], "Other workspace")

    listing = client.get("/api/notifications", headers=account["headers"])
    assert listing.status_code == 200, listing.text
    assert {note["id"] for note in listing.json()} == {workspace_note, personal_note}

    unread = client.get("/api/notifications?unread_only=true", headers=account["headers"])
    assert unread.status_code == 200, unread.text
    assert {note["id"] for note in unread.json()} == {workspace_note, personal_note}

    dashboard = client.get("/api/dashboard", headers=account["headers"])
    assert dashboard.status_code == 200, dashboard.text
    assert {note["id"] for note in dashboard.json()["notifications"]} == {workspace_note, personal_note}

    assert client.post("/api/notifications/read-all", headers=account["headers"]).status_code == 204
    assert client.get("/api/notifications?unread_only=true", headers=account["headers"]).json() == []
