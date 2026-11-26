from __future__ import annotations


def test_bulk_zip_requires_matching_exports(client, account):
    response = client.get("/api/exports/zip?ids=does-not-exist", headers=account["headers"])
    assert response.status_code == 404


def test_bulk_zip_rejects_empty_selection(client, account):
    response = client.get("/api/exports/zip?ids=,", headers=account["headers"])
    assert response.status_code == 400

