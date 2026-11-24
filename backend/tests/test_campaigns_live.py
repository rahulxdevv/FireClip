from __future__ import annotations

from app.database import session_scope
from app.models import LiveStream
from app.services import captions, live


def test_campaign_crud_and_video_binding(client, account, uploaded_video):
    headers = account["headers"]
    response = client.post(
        "/api/campaigns",
        headers=headers,
        json={
            "name": "Launch stories",
            "brief": "Find contrarian founder lessons with concrete numbers.",
            "aspect_ratio": "4:5",
            "target_duration_ms": 30000,
            "clip_count": 4,
            "min_score": 20,
            "auto_approve": True,
            "auto_render": False,
            "brand": {"accent_color": "#22cc88", "logo_text": "@studio"},
        },
    )
    assert response.status_code == 201, response.text
    campaign = response.json()
    assert campaign["status"] == "active"
    assert campaign["brand"]["accent_color"] == "#22cc88"

    listing = client.get("/api/campaigns", headers=headers)
    assert listing.status_code == 200
    assert any(item["id"] == campaign["id"] for item in listing.json())

    response = client.patch(
        f"/api/campaigns/{campaign['id']}",
        headers=headers,
        json={"status": "paused", "auto_approve": False},
    )
    assert response.status_code == 200, response.text

    response = client.patch(
        f"/api/campaigns/{campaign['id']}",
        headers=headers,
        json={"auto_render": True},
    )
    assert response.status_code == 422, response.text

    response = client.post(
        f"/api/campaigns/{campaign['id']}/videos",
        headers=headers,
        json={"video_ids": [uploaded_video["id"]]},
    )
    assert response.status_code == 200, response.text
    detail = response.json()
    assert [video["id"] for video in detail["videos"]] == [uploaded_video["id"]]
    assert detail["video_count"] == 1

    response = client.delete(
        f"/api/campaigns/{campaign['id']}/videos/{uploaded_video['id']}",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["videos"] == []

    response = client.delete(f"/api/campaigns/{campaign['id']}", headers=headers)
    assert response.status_code == 204, response.text
    assert client.get(f"/api/campaigns/{campaign['id']}", headers=headers).status_code == 404


def test_campaign_rejects_unknown_brand_fields(client, account):
    response = client.post(
        "/api/campaigns",
        headers=account["headers"],
        json={"name": "Bad brand", "brand": {"logo_url": "https://example.com/logo.png"}},
    )
    assert response.status_code == 422

    response = client.post(
        "/api/campaigns",
        headers=account["headers"],
        json={"name": "Bad color", "brand": {"accent_color": "red"}},
    )
    assert response.status_code == 422


def test_caption_styles_cover_extended_animation_and_renderer():
    names = {name for name, _ in captions.BUILTIN_STYLES}
    assert len(names) >= 20
    assert {"Fire", "Neon", "Terminal", "Bounce", "Retro", "Elegant"} <= names

    style = {
        "font": "Georgia",
        "font_size": 58,
        "text_color": "#ffeeaa",
        "highlight_color": "#ff3355",
        "animation": "bounce",
        "italic": True,
        "letter_spacing": 2,
        "box": False,
    }
    ass = captions.build_caption_ass(
        [captions.SegmentData(start_ms=0, end_ms=1600, text="hello world", words=[], confidence=1.0)],
        style,
        clip_start_ms=0,
        clip_end_ms=2000,
        width=1080,
        height=1920,
    )
    assert "Georgia" in ass
    style_line = next(line for line in ass.splitlines() if line.startswith("Style:"))
    fields = style_line.split(",")
    assert fields[7] == "1"  # bold
    assert fields[8] == "1"  # italic
    assert fields[13] == "2"  # letter spacing
    assert "\\fscx65" in ass and "\\fscy112" in ass

    overlay = captions.build_overlay_ass(
        [
            {
                "type": "text",
                "text": "@studio",
                "x": 0.5,
                "y": 0.07,
                "outline_color": "#22cc88",
                "outline_width": 4,
            }
        ],
        clip_start_ms=0,
        clip_end_ms=2000,
        width=1080,
        height=1920,
    )
    assert "\\3c&H0088cc22" in overlay


def test_live_monitor_records_only_when_live(client, account, monkeypatch):
    monkeypatch.setattr(live.sources, "ytdlp_available", lambda: True)
    monkeypatch.setattr(live.sources, "fetch_live_state", lambda url: True)
    monkeypatch.setattr(live, "enqueue", lambda job_id: None)

    with session_scope() as db:
        stream = LiveStream(
            workspace_id=account["workspace_id"],
            created_by=account["user_id"],
            platform="custom",
            url="https://example.com/public-live",
            title="Auto capture",
            status="monitoring",
            auto_record=True,
            auto_clip=True,
        )
        db.add(stream)
        db.flush()
        stream_id = stream.id

    assert live.check_due_live_streams() >= 1

    streams = client.get("/api/live-streams", headers=account["headers"]).json()
    stream = next(item for item in streams if item["id"] == stream_id)
    assert stream["auto_record"] is True
    assert stream["auto_clip"] is True

    updated = client.get("/api/live-streams", headers=account["headers"]).json()
    row = next(item for item in updated if item["id"] == stream_id)
    assert row["status"] == "recording"
    assert row["recording_video_id"]
    assert row["last_checked_at"] is not None

    # A second immediate pass respects the per-stream check interval.
    assert live.check_due_live_streams() == 0
