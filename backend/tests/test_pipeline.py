"""End-to-end pipeline test using a real generated video and real FFmpeg."""
from __future__ import annotations

import json
import subprocess
import time

import pytest

from tests.conftest import wait_for_job


def _wait_for_clips(client, video_id, headers, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        clips = client.get(f"/api/clips?video_id={video_id}", headers=headers).json()
        if clips:
            return clips
        time.sleep(0.3)
    raise AssertionError("analysis produced no clips")


@pytest.fixture(scope="module")
def pipeline(client):
    from tests.conftest import register, wait_for_video

    account = register(client, "Pipeline")
    headers = account["headers"]
    sample = __import__("tests.conftest", fromlist=["TEST_DATA"]).TEST_DATA / "sample.mp4"
    if not sample.exists():
        from tests.conftest import _make_video

        _make_video(sample, seconds=14, color="black")
    with open(sample, "rb") as handle:
        response = client.post(
            "/api/videos/upload",
            files={"file": ("sample.mp4", handle, "video/mp4")},
            headers=headers,
        )
    assert response.status_code == 201, response.text
    video = wait_for_video(client, response.json()["id"], headers)
    assert video["status"] == "ready", video.get("error_message")
    clips = _wait_for_clips(client, video["id"], headers)
    return {"account": account, "video": video, "clips": clips, "headers": headers}


def test_ingest_metadata(pipeline):
    video = pipeline["video"]
    assert video["duration_seconds"] == pytest.approx(14, abs=0.5)
    assert video["width"] == 480 and video["height"] == 270
    assert video["has_audio"] is True
    assert video["mime_type"].startswith("video/")


def test_transcript_has_words_and_speakers(client, pipeline):
    headers = pipeline["headers"]
    response = client.get(f"/api/videos/{pipeline['video']['id']}/transcript", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "completed"
    assert data["engine"] == "mock"
    assert len(data["segments"]) >= 4
    assert any(segment["words"] for segment in data["segments"])
    assert data["full_text"]
    assert data["speakers"]


def test_clip_candidates_are_explainable(client, pipeline):
    clips = pipeline["clips"]
    assert len(clips) >= 1
    clip = clips[0]
    assert 0 <= clip["virality_score"] <= 100
    assert clip["explanation"]
    assert clip["hook"]
    assert clip["signals"]
    assert clip["end_ms"] > clip["start_ms"]
    assert clip["duration_ms"] == clip["end_ms"] - clip["start_ms"]
    assert "loudness" in clip["explanation"].lower()


def test_clip_actions_and_content(client, pipeline):
    headers = pipeline["headers"]
    clip = pipeline["clips"][0]
    approved = client.post(f"/api/clips/{clip['id']}/approve", headers=headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    content = client.post(f"/api/clips/{clip['id']}/content", headers=headers)
    assert content.status_code == 200, content.text
    body = content.json()
    assert body["titles"] and body["hashtags"] and body["captions"]["youtube"]
    assert body["provider"] in {"heuristic", "openai", "anthropic", "gemini", "ollama"}

    edited = client.patch(
        f"/api/clips/{clip['id']}", json={"title": "A sharper title"}, headers=headers
    )
    assert edited.status_code == 200
    assert edited.json()["title"] == "A sharper title"


def test_editor_and_render_produce_vertical_video(client, pipeline):
    headers = pipeline["headers"]
    clip = pipeline["clips"][0]
    editor = client.post(f"/api/clips/{clip['id']}/editor", json={}, headers=headers)
    assert editor.status_code == 200, editor.text
    project = editor.json()
    assert project["width"] == 1080 and project["height"] == 1920
    assert project["trim_start_ms"] == clip["start_ms"]

    updated = client.patch(
        f"/api/editors/{project['id']}",
        json={"caption_overrides": {"highlight_color": "#ff6a1f", "font_size": 70}},
        headers=headers,
    )
    assert updated.status_code == 200

    render = client.post(
        f"/api/editors/{project['id']}/render",
        json={"preset": "tiktok", "format": "mp4"},
        headers=headers,
    )
    assert render.status_code == 202, render.text
    job_id = render.json()["id"]
    deadline = time.time() + 180
    while time.time() < deadline:
        detail = client.get(f"/api/renders/{job_id}", headers=headers).json()
        if detail["status"] in {"completed", "failed", "cancelled"}:
            break
        time.sleep(0.4)
    assert detail["status"] == "completed", detail.get("error_message")
    assert detail["download_url"]
    assert detail["output_size_bytes"] > 10000

    download = client.get(detail["download_url"], headers=headers)
    assert download.status_code == 200
    out = __import__("tests.conftest", fromlist=["TEST_DATA"]).TEST_DATA / "rendered.mp4"
    out.write_bytes(download.content)

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(out)],
        capture_output=True,
        text=True,
    )
    meta = json.loads(probe.stdout)
    video_stream = next(s for s in meta["streams"] if s["codec_type"] == "video")
    assert video_stream["width"] == 1080
    assert video_stream["height"] == 1920
    assert any(s["codec_type"] == "audio" for s in meta["streams"])
    assert float(meta["format"]["duration"]) == pytest.approx(clip["duration_ms"] / 1000, abs=0.6)

    exports = client.get("/api/exports", headers=headers).json()
    assert any(export["render_job_id"] == job_id for export in exports)

    # Burned captions must be visible: sample orange/white caption pixels on black.
    import cv2

    capture = cv2.VideoCapture(str(out))
    fps = capture.get(cv2.CAP_PROP_FPS) or 24
    capture.set(cv2.CAP_PROP_POS_FRAMES, int(fps * 0.5))
    ok, frame = capture.read()
    capture.release()
    assert ok
    assert frame.shape[0] == 1920 and frame.shape[1] == 1080
    bright = (frame.astype("int32").sum(axis=2) > 300).sum()
    assert bright > 500, "captions were not burned into the rendered frame"


def test_range_streaming(client, pipeline):
    headers = pipeline["headers"]
    video_id = pipeline["video"]["id"]
    response = client.get(f"/api/videos/{video_id}/stream", headers={**headers, "Range": "bytes=0-1023"})
    assert response.status_code == 206
    assert len(response.content) == 1024
    assert response.headers["content-range"].startswith("bytes 0-1023/")

    thumb = client.get(f"/api/videos/{video_id}/thumbnail", headers=headers)
    assert thumb.status_code == 200
    assert thumb.headers["content-type"].startswith("image/")


def test_dashboard_reflects_real_data(client, pipeline):
    headers = pipeline["headers"]
    dashboard = client.get("/api/dashboard", headers=headers)
    assert dashboard.status_code == 200
    counts = dashboard.json()["counts"]
    assert counts["videos"] >= 1
    assert counts["clips"] >= 1
    assert counts["renders"] >= 1
    assert counts["exports"] >= 1
    assert dashboard.json()["recent_clips"]
