from __future__ import annotations


def test_user_caption_style_can_be_renamed_and_deleted(client, account):
    headers = account["headers"]
    created = client.post(
        "/api/caption-styles",
        headers=headers,
        json={"name": "Studio look", "config": {"font_size": 62, "text_color": "#ffffff"}},
    )
    assert created.status_code == 201, created.text
    style = created.json()
    assert style["is_builtin"] is False

    updated = client.patch(
        f"/api/caption-styles/{style['id']}",
        headers=headers,
        json={"name": "Studio look v2", "config": {"font_size": 68, "look": {"mode": "gameplay"}}},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Studio look v2"
    assert updated.json()["config"]["font_size"] == 68
    assert updated.json()["config"]["look"]["mode"] == "gameplay"
    deleted = client.delete(f"/api/caption-styles/{style['id']}", headers=headers)
    assert deleted.status_code == 204
    listing = client.get("/api/caption-styles", headers=headers)
    assert listing.status_code == 200
    assert all(item["id"] != style["id"] for item in listing.json())


def test_builtin_caption_style_is_read_only(client, account):
    headers = account["headers"]
    listing = client.get("/api/caption-styles", headers=headers)
    builtin = next(item for item in listing.json() if item["is_builtin"])
    assert client.patch(
        f"/api/caption-styles/{builtin['id']}",
        headers=headers,
        json={"name": "Mine now"},
    ).status_code == 403
    assert client.delete(f"/api/caption-styles/{builtin['id']}", headers=headers).status_code == 403

