"""Test environment. Set env vars before importing the application."""
from __future__ import annotations

import os
import subprocess
import tempfile
import uuid
from pathlib import Path

import pytest

TEST_DATA = Path(tempfile.mkdtemp(prefix="fireclip-test-"))
os.environ["DATA_DIR"] = str(TEST_DATA)
os.environ["DATABASE_URL"] = f"sqlite:///{(TEST_DATA / 'test.db').as_posix()}"
os.environ["JWT_SECRET"] = "test-secret-0123456789abcdef-0123456789abcdef"
os.environ["ALLOW_MOCK_TRANSCRIPTION"] = "true"
os.environ["TRANSCRIPTION_ENGINE"] = "mock"
os.environ["JOB_RUNNER"] = "inline"
os.environ["AUTO_MIGRATE"] = "true"
os.environ["AUTO_PIPELINE"] = "true"
# The sample fixture is a still colour card; still-screen skipping has its own tests.
os.environ["STATIC_SCREEN_FILTER"] = "false"
os.environ["RATE_LIMIT_AUTH_PER_MINUTE"] = "1000"
os.environ["RATE_LIMIT_API_PER_MINUTE"] = "10000"
os.environ["OPENAI_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["AI_PROVIDER"] = "auto"
os.environ["APP_ENV"] = "test"
os.environ["FRONTEND_URL"] = "http://localhost:3000"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import PipelineJob, SourceVideo  # noqa: E402


def _make_video(path: Path, seconds: int = 12, color: str = "black") -> Path:
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostdin", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:size=480x270:rate=24",
            "-f", "lavfi", "-i", "sine=frequency=330:sample_rate=44100",
            "-t", str(seconds),
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def sample_video() -> Path:
    path = TEST_DATA / "sample.mp4"
    if not path.exists():
        _make_video(path, seconds=14, color="black")
    return path


def register(client: TestClient, name: str = "Test") -> dict:
    email = f"user-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "StrongPass123",
            "name": name,
            "workspace_name": f"{name} Studio",
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    return {
        "email": email,
        "password": "StrongPass123",
        "user_id": data["user"]["id"],
        "workspace_id": data["active_workspace_id"],
        "headers": {"X-Workspace-Id": data["active_workspace_id"]},
    }


@pytest.fixture
def account(client) -> dict:
    return register(client, "Tester")


def wait_for_job(client: TestClient, job_id: str, headers: dict, timeout: float = 180) -> dict:
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get("/api/jobs", headers=headers)
        for job in response.json():
            if job["id"] == job_id:
                if job["status"] in {"completed", "failed", "cancelled"}:
                    return job
        time.sleep(0.25)
    raise AssertionError(f"job {job_id} did not finish within {timeout}s")


def wait_for_video(client: TestClient, video_id: str, headers: dict, timeout: float = 180) -> dict:
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        data = client.get(f"/api/videos/{video_id}", headers=headers).json()
        if data["status"] in {"ready", "error"}:
            return data
        time.sleep(0.25)
    raise AssertionError(f"video {video_id} never reached a terminal state")


@pytest.fixture
def uploaded_video(client, account, sample_video):
    with open(sample_video, "rb") as handle:
        response = client.post(
            "/api/videos/upload",
            files={"file": ("sample.mp4", handle, "video/mp4")},
            headers=account["headers"],
        )
    assert response.status_code == 201, response.text
    video = wait_for_video(client, response.json()["id"], account["headers"])
    assert video["status"] == "ready", video.get("error_message")
    return video
