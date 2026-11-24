"""Tests for accounts, review comments, sharing, billing and webhooks."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import timedelta

from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.models import (
    CandidateClip,
    EditingProject,
    ExportedVideo,
    RenderJob,
    ShareLink,
    User,
    Workspace,
    utcnow,
)
from app.services import webhooks as hook_service
from app.services.tokens import issue_email_token

from .conftest import register


def _user(db, email: str) -> User:
    return db.query(User).filter(User.email == email).one()


def test_email_verification_and_password_reset(client: TestClient, account: dict):
    with SessionLocal() as db:
        user = _user(db, account["email"])
        verify_raw = issue_email_token(
            db, email=user.email, kind="verify", user_id=user.id, expires_delta=timedelta(hours=1)
        )
        db.commit()
    response = client.post("/api/auth/verify-email", json={"token": verify_raw})
    assert response.status_code == 200, response.text
    assert response.json()["verified"] is True
    session = client.get("/api/auth/me", headers=account["headers"]).json()
    assert session["user"]["email_verified_at"] is not None

    with SessionLocal() as db:
        user = _user(db, account["email"])
        reset_raw = issue_email_token(
            db, email=user.email, kind="reset", user_id=user.id, expires_delta=timedelta(minutes=30)
        )
        db.commit()
    response = client.post(
        "/api/auth/reset-password",
        json={"token": reset_raw, "new_password": "BrandNewPass456"},
    )
    assert response.status_code == 200, response.text
    response = client.post(
        "/api/auth/login",
        json={"email": account["email"], "password": "BrandNewPass456"},
    )
    assert response.status_code == 200, response.text
    # A used reset token cannot be replayed.
    assert client.post(
        "/api/auth/reset-password",
        json={"token": reset_raw, "new_password": "AnotherPass789"},
    ).status_code == 400


def test_forgot_password_does_not_leak_accounts(client: TestClient):
    response = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["dev_link"] is None


def test_require_email_verification_blocks_login(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "require_email_verification", True)
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "mail_from", "")
    client.cookies.clear()
    email = f"unverified-{int(time.time() * 1000)}@example.com"
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "VerifyPass123", "name": "Unverified", "workspace_name": "Verify Lab"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["verification_required"] is True
    assert body["verification_link"] and "token=" in body["verification_link"]
    assert client.get("/api/auth/me").status_code == 401
    blocked = client.post("/api/auth/login", json={"email": email, "password": "VerifyPass123"})
    assert blocked.status_code == 403, blocked.text
    token = body["verification_link"].split("token=", 1)[1]
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 200
    allowed = client.post("/api/auth/login", json={"email": email, "password": "VerifyPass123"})
    assert allowed.status_code == 200, allowed.text

def test_workspace_invitation_flow(client: TestClient, account: dict, monkeypatch):
    monkeypatch.setattr(settings, "debug", True)
    invited_email = f"invitee-{int(time.time() * 1000)}@example.com"
    response = client.post(
        f"/api/workspaces/{account['workspace_id']}/invites",
        json={"email": invited_email, "role": "editor"},
        headers=account["headers"],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "invited"
    link = body.get("dev_link")
    assert link and "/invite/" in link
    token = link.split("/invite/", 1)[1]

    preview = client.get(f"/api/auth/invite/{token}")
    assert preview.status_code == 200, preview.text
    assert preview.json()["workspace_name"]
    assert preview.json()["account_exists"] is False

    accepted = client.post(
        f"/api/auth/invite/{token}/accept",
        json={"name": "Invitee", "password": "InviteePass123"},
    )
    assert accepted.status_code == 200, accepted.text
    assert any(
        workspace["id"] == account["workspace_id"] for workspace in accepted.json()["workspaces"]
    )
    # Restore the original owner session for later tests.
    client.post(
        "/api/auth/login",
        json={"email": account["email"], "password": "StrongPass123"},
    )


def _make_clip(workspace_id: str, video_id: str, title: str) -> CandidateClip:
    with SessionLocal() as db:
        clip = CandidateClip(
            workspace_id=workspace_id,
            video_id=video_id,
            start_ms=0,
            end_ms=5000,
            duration_ms=5000,
            title=title,
            transcript_text="hello world",
            # Approved so a late auto-analysis pass cannot replace these review fixtures.
            status="approved",
        )
        db.add(clip)
        db.commit()
        db.refresh(clip)
        return clip


def test_clip_comments_and_bulk_review(client: TestClient, account: dict, uploaded_video: dict):
    first = _make_clip(account["workspace_id"], uploaded_video["id"], "First review clip")
    second = _make_clip(account["workspace_id"], uploaded_video["id"], "Second review clip")

    blank = client.post(
        f"/api/clips/{first.id}/comments",
        json={"body": "   "},
        headers=account["headers"],
    )
    assert blank.status_code == 422

    created = client.post(
        f"/api/clips/{first.id}/comments",
        json={"body": "Tighten the hook and keep the captions."},
        headers=account["headers"],
    )
    assert created.status_code == 201, created.text
    comment = created.json()
    assert comment["mine"] is True

    listed = client.get(f"/api/clips/{first.id}/comments", headers=account["headers"])
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    resolved = client.patch(
        f"/api/clips/{first.id}/comments/{comment['id']}",
        json={"resolved": True},
        headers=account["headers"],
    )
    assert resolved.status_code == 200
    assert resolved.json()["resolved_at"] is not None

    detail = client.get(f"/api/clips/{first.id}", headers=account["headers"])
    assert detail.status_code == 200
    assert detail.json()["comment_count"] == 1
    assert detail.json()["open_comment_count"] == 0

    bulk = client.post(
        "/api/clips/bulk",
        json={"action": "approve", "clip_ids": [first.id, second.id]},
        headers=account["headers"],
    )
    assert bulk.status_code == 200, bulk.text
    assert bulk.json()["updated"] == 2

    deleted = client.post(
        "/api/clips/bulk",
        json={"action": "delete", "clip_ids": [first.id, second.id]},
        headers=account["headers"],
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 2


def test_share_links_are_revocable_and_password_protected(
    client: TestClient, account: dict, uploaded_video: dict
):
    with SessionLocal() as db:
        project = EditingProject(
            workspace_id=account["workspace_id"],
            video_id=uploaded_video["id"],
            created_by=account["user_id"],
            name="Share test project",
        )
        db.add(project)
        db.flush()
        render = RenderJob(
            workspace_id=account["workspace_id"],
            editing_project_id=project.id,
            created_by=account["user_id"],
            status="completed",
        )
        db.add(render)
        db.flush()
        export = ExportedVideo(
            workspace_id=account["workspace_id"],
            render_job_id=render.id,
            title="Shared clip",
            filename="shared.mp4",
            storage_key="exports/missing.mp4",
            format="mp4",
            width=1080,
            height=1920,
            duration_ms=5000,
            size_bytes=1000,
        )
        db.add(export)
        db.commit()
        db.refresh(export)
        export_id = export.id

    created = client.post(
        f"/api/exports/{export_id}/shares",
        json={"expires_in_days": 7, "password": "sharepass"},
        headers=account["headers"],
    )
    assert created.status_code == 201, created.text
    share = created.json()
    assert share["has_password"] is True

    locked = client.get(f"/api/public/shares/{share['token']}")
    assert locked.status_code == 200
    assert locked.json()["locked"] is True

    wrong = client.post(f"/api/public/shares/{share['token']}/unlock", json={"password": "nope"})
    assert wrong.status_code == 403

    unlocked = client.post(
        f"/api/public/shares/{share['token']}/unlock", json={"password": "sharepass"}
    )
    assert unlocked.status_code == 200, unlocked.text
    assert unlocked.json()["locked"] is False
    assert "media_url" in unlocked.json()

    revoked = client.delete(f"/api/shares/{share['id']}", headers=account["headers"])
    assert revoked.status_code == 204
    assert client.get(f"/api/public/shares/{share['token']}").status_code == 404


def test_billing_plans_and_unconfigured_checkout(client: TestClient, account: dict):
    response = client.get("/api/billing/plans", headers=account["headers"])
    assert response.status_code == 200
    body = response.json()
    assert [plan["id"] for plan in body["plans"]] == ["free", "starter", "studio", "agency"]
    assert body["current"]["plan"]
    if not body["provider"]["available"]:
        checkout = client.post(
            "/api/billing/checkout",
            json={"plan": "studio", "interval": "month"},
            headers=account["headers"],
        )
        assert checkout.status_code == 503


def test_stripe_webhook_signature(monkeypatch):
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test_secret")
    payload = json.dumps(
        {"id": "evt_test", "type": "invoice.paid", "data": {"object": {"id": "in_test"}}}
    ).encode()
    timestamp = int(time.time())
    expected = hmac.new(
        b"whsec_test_secret", f"{timestamp}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    from app.services.billing import verify_webhook

    event = verify_webhook(payload, f"t={timestamp},v1={expected}")
    assert event["id"] == "evt_test"
    try:
        verify_webhook(payload, f"t={timestamp},v1=deadbeef")
    except Exception as exc:
        assert "signature" in str(exc).lower()
    else:
        raise AssertionError("bad signature should fail")


def test_webhook_management(client: TestClient, account: dict, monkeypatch):
    monkeypatch.setattr(hook_service, "validate_endpoint_url", lambda url: url)
    events = client.get("/api/webhooks", headers=account["headers"])
    assert events.status_code == 200
    assert "clip.approved" in events.json()["events"]

    created = client.post(
        "/api/webhooks",
        json={"url": "https://example.com/hook", "events": ["clip.approved"]},
        headers=account["headers"],
    )
    assert created.status_code == 201, created.text
    endpoint = created.json()
    assert endpoint["secret"].startswith("whsec_")
    assert endpoint["events"] == ["clip.approved"]

    unknown = client.post(
        "/api/webhooks",
        json={"url": "https://example.com/other", "events": ["not.real"]},
        headers=account["headers"],
    )
    assert unknown.status_code == 400

    disabled = client.patch(
        f"/api/webhooks/{endpoint['id']}",
        json={"enabled": False},
        headers=account["headers"],
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False

    assert client.delete(
        f"/api/webhooks/{endpoint['id']}", headers=account["headers"]
    ).status_code == 204