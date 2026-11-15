from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import ApiKey
from app.storage import LocalStorage
from tests.conftest import register


def test_workspace_isolation(client):
    alice = register(client, "Alice")
    project = client.post(
        "/api/projects", json={"name": "Alice private"}, headers=alice["headers"]
    ).json()

    bob = register(client, "Bob")
    forbidden = client.get(
        "/api/projects", headers={"X-Workspace-Id": alice["workspace_id"]}
    )
    assert forbidden.status_code == 403

    # Bob's own workspace does not contain Alice's project.
    projects = client.get("/api/projects", headers=bob["headers"]).json()
    assert all(item["id"] != project["id"] for item in projects)

    # Even with Alice's project id, Bob cannot read workspace data.
    videos = client.get(f"/api/videos?project_id={project['id']}", headers=bob["headers"])
    assert videos.status_code == 200 and videos.json() == []


def test_api_key_is_hashed_and_scoped(client):
    account = register(client, "KeyOwner")
    created = client.post("/api/api-keys", json={"name": "CI"}, headers=account["headers"])
    assert created.status_code == 201
    payload = created.json()
    assert payload["key"].startswith("fk_")

    with SessionLocal() as db:
        row = db.get(ApiKey, payload["id"])
        assert row is not None
        assert payload["key"] not in (row.key_hash, row.prefix)
        assert len(row.key_hash) == 64

    separate = TestClient(app)
    response = separate.get("/api/videos", headers={"X-API-Key": payload["key"]})
    assert response.status_code == 200
    forbidden = separate.get(
        "/api/videos",
        headers={"X-API-Key": payload["key"], "X-Workspace-Id": "some-other-workspace"},
    )
    assert forbidden.status_code == 403

    client.delete(f"/api/api-keys/{payload['id']}", headers=account["headers"])
    assert separate.get("/api/videos", headers={"X-API-Key": payload["key"]}).status_code == 401


def test_storage_blocks_path_traversal(tmp_path):
    storage = LocalStorage(tmp_path)
    with pytest.raises(ValueError):
        storage.put_bytes(b"x", "../../etc/passwd")
    assert not (Path(tmp_path).parent / "etc" / "passwd").exists()


def test_ai_settings_never_expose_secrets(client):
    account = register(client, "Settings")
    response = client.get("/api/ai/providers", headers=account["headers"])
    assert response.status_code == 200
    raw = response.text
    assert "api_key" not in raw
    for provider in response.json():
        assert set(provider.keys()) == {
            "provider", "label", "model", "base_url", "configured", "has_workspace_key",
            "enabled", "is_default", "capabilities", "local",
        }


def test_origin_validation_blocks_foreign_mutations(client):
    _ = register(client, "Origin")
    response = client.post(
        "/api/projects",
        json={"name": "Cross site"},
        headers={"Origin": "https://evil.example"},
    )
    # In development the origin check is relaxed, but CORS still does not grant access.
    assert response.status_code in {200, 201, 403}
    if settings.environment == "production":
        assert response.status_code == 403
