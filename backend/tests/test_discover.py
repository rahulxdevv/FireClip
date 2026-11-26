from __future__ import annotations

from app.services import sources


def test_discover_streamers_returns_public_results(client, account, monkeypatch):
    seen: dict[str, object] = {}

    def fake_search(query: str, *, limit: int = 12, live_only: bool = False):
        seen.update(query=query, limit=limit, live_only=live_only)
        return [
            {
                "platform": "youtube",
                "channel": "Night Shift",
                "channel_url": "https://www.youtube.com/@nightshift",
                "title": "Late night ranked",
                "video_url": "https://www.youtube.com/watch?v=abc",
                "thumbnail_url": "https://example.com/thumb.jpg",
                "live": True,
                "viewers": 1200,
                "duration_seconds": 5400.0,
            }
        ]

    monkeypatch.setattr(sources, "ytdlp_available", lambda: True)
    monkeypatch.setattr(sources, "search_streamers", fake_search)
    response = client.get(
        "/api/discover/streamers?q=night%20shift&live_only=true&limit=6",
        headers=account["headers"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "yt-dlp"
    assert body["items"][0]["channel"] == "Night Shift"
    assert seen == {"query": "night shift", "limit": 6, "live_only": True}


def test_discover_streamers_reports_missing_ytdlp(client, account, monkeypatch):
    monkeypatch.setattr(sources, "ytdlp_available", lambda: False)
    response = client.get("/api/discover/streamers?q=anything", headers=account["headers"])
    assert response.status_code == 503
    assert "yt-dlp" in response.json()["detail"]

