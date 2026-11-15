from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.database import SessionLocal
from app.models import AnalyticsRecord, PublishingJob, SocialAccount
from app.security import encrypt_secret
from app.services import analytics, publishing
from tests.conftest import register


def test_connect_without_credentials_is_honest(client):
    account = register(client, "Social")
    response = client.get("/api/publishing/connect/youtube", headers=account["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert body["authorize_url"] is None
    assert "not configured" in body["message"].lower()


def test_oauth_url_and_state_roundtrip(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "client-id.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "google_client_secret", "secret")
    configured, url, message = publishing.authorize_url("youtube", "ws-1", "user-1")
    assert configured is True
    assert "accounts.google.com" in url
    assert "state=" in url
    assert message == ""
    from urllib.parse import parse_qs, urlparse

    state = parse_qs(urlparse(url).query)["state"][0]
    payload = publishing.decode_state(state, "youtube")
    assert payload["ws"] == "ws-1"
    assert payload["sub"] == "user-1"
    with pytest.raises(publishing.PublishError):
        publishing.decode_state(state, "tiktok")


def test_analytics_are_empty_not_invented(client):
    account = register(client, "Analytics")
    response = client.get("/api/analytics/overview", headers=account["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["totals"]["views"] == 0
    assert body["totals"]["measured_posts"] == 0
    assert body["series"] == []
    assert any("never estimates" in note for note in body["notes"])

    sync = client.post("/api/analytics/sync", headers=account["headers"])
    assert sync.status_code == 200
    assert sync.json()["synced"] == 0
    assert sync.json()["messages"]


def test_manual_analytics_requires_real_post(client, account):
    response = client.post(
        "/api/analytics/entry",
        json={"publishing_job_id": "does-not-exist", "views": 100},
        headers=account["headers"],
    )
    assert response.status_code == 404


def test_publishing_requires_connected_account(client, account):
    response = client.post(
        "/api/publishing/jobs",
        json={"exported_video_id": "missing", "social_account_id": "missing", "caption": "hi"},
        headers=account["headers"],
    )
    assert response.status_code == 404
    jobs = client.get("/api/publishing/jobs", headers=account["headers"])
    assert jobs.status_code == 200 and jobs.json() == []


def test_youtube_metrics_parsing(monkeypatch):
    account = SocialAccount(
        id="acct",
        workspace_id="ws",
        platform="youtube",
        account_name="Channel",
        external_id="channel",
        access_token_encrypted=encrypt_secret("token"),
        status="connected",
        connected_by="user",
    )
    job = PublishingJob(
        id="job", workspace_id="ws", exported_video_id="export", social_account_id="acct",
        platform="youtube", external_post_id="abc123", status="published", created_by="user",
    )

    class Response:
        status_code = 200

        def json(self):
            return {"items": [{"statistics": {"viewCount": "1200", "likeCount": "44", "commentCount": "7"}}]}

    monkeypatch.setattr(publishing, "_maybe_refresh", lambda db, acct: "token")
    monkeypatch.setattr(publishing.httpx, "get", lambda *a, **k: Response())
    metrics = publishing.fetch_metrics(None, account, job)
    assert metrics == {"views": 1200, "likes": 44, "comments": 7, "shares": 0}
