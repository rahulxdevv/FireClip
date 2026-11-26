from __future__ import annotations

import pytest

from app.config import settings
from app.database import SessionLocal
from app.services import storage_guard


def test_capacity_allows_small_workspace(account):
    with SessionLocal() as db:
        storage_guard.check_capacity(db, account["workspace_id"], 1024)


def test_capacity_rejects_workspace_over_limit(account, monkeypatch):
    monkeypatch.setattr(settings, "max_workspace_storage_gb", 0.000001)
    with SessionLocal() as db:
        with pytest.raises(storage_guard.StorageGuardError):
            storage_guard.check_capacity(db, account["workspace_id"], 10_000_000)


def test_system_status_reports_workspace_storage(client, account):
    response = client.get("/api/system/status", headers=account["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["workspace_storage_bytes"] >= 0
    assert "disk_free_gb" in body


def test_disk_guard_reports_low_space(monkeypatch):
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "min_free_disk_gb", 10_000_000.0)
    with pytest.raises(storage_guard.StorageGuardError):
        storage_guard.check_disk(0)

