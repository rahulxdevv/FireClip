from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app import tasks
from app.config import settings
from app.database import session_scope
from app.models import (
    Campaign,
    EditingProject,
    ExportedVideo,
    PublishingJob,
    RenderJob,
    SocialAccount,
)
from app.services import auto_publish, campaign_feed, captions, render, translation


def test_campaign_feed_normalizes_brand_guidelines_and_skips_inactive():
    campaigns = campaign_feed.normalize(
        {
            "campaigns": [
                {
                    "id": "summer-2026",
                    "title": "Summer launch",
                    "description": "Short launch clips",
                    "guidelines": "Mention the discount code.",
                    "hashtags": ["launch", "#summer"],
                    "brand": {"accent_color": "#22cc88", "headline": "Launch week"},
                    "clip_count": 12,
                    "min_score": 55,
                    "ends_at": "2099-01-01T00:00:00Z",
                },
                {"id": "ended", "name": "Ended", "status": "ended"},
                {"id": "draft", "name": "Draft", "status": "draft"},
            ]
        }
    )
    assert len(campaigns) == 1
    item = campaigns[0]
    assert item["external_id"] == "summer-2026"
    assert item["brief"] == "Mention the discount code."
    assert item["brand"]["headline"] == "Launch week"
    assert item["hashtags"] == ["#launch", "#summer"]
    assert item["clip_count"] == 12
    assert item["min_score"] == 55


def test_campaign_feed_rejects_private_hosts():
    with pytest.raises(campaign_feed.CampaignFeedError):
        campaign_feed._safe_url("http://127.0.0.1/campaigns.json")
    with pytest.raises(campaign_feed.CampaignFeedError):
        campaign_feed._safe_url("http://localhost/campaigns.json")


def test_campaign_logo_overlay_uses_source_timestamps(monkeypatch):
    class Storage:
        def exists(self, key):
            return True

    monkeypatch.setattr(tasks, "get_storage", lambda: Storage())
    overlays = tasks._campaign_overlays(
        brand_mark="",
        brand_accent="#ff6a1f",
        headline="Headline",
        cta="",
        hashtags="",
        logo_key="assets/ws/logo.png",
        logo_x=0.5,
        start_ms=30000,
        end_ms=40000,
    )
    assert overlays[0]["start_ms"] == 30000
    assert overlays[0]["end_ms"] == 40000
    assert overlays[0]["source_ms"] is True


def test_translation_keeps_line_count_and_reports_bad_provider_output():
    class Provider:
        name = "test-provider"
        model = "test-model"

        def __init__(self, values):
            self.values = values

        def complete(self, *args, **kwargs):
            return json.dumps({"translations": self.values})

    segments = [
        SimpleNamespace(text="Hello", start_ms=0, end_ms=500),
        SimpleNamespace(text="World", start_ms=500, end_ms=1000),
    ]
    result = translation.translate_segments(Provider(["Hola", "Mundo"]), segments, "es")
    assert result["language"] == "es"
    assert [line["text"] for line in result["segments"]] == ["Hola", "Mundo"]
    with pytest.raises(translation.TranslationError):
        translation.translate_segments(Provider(["solo una"]), segments, "es")


def test_campaign_feed_rejects_bad_shapes():
    try:
        campaign_feed.normalize({"unexpected": True})
    except campaign_feed.CampaignFeedError as exc:
        assert "list of campaigns" in str(exc)
    else:
        raise AssertionError("expected a feed shape error")


def test_next_slot_is_strictly_in_the_future():
    now = datetime(2026, 8, 3, 18, 30, tzinfo=timezone.utc)
    assert auto_publish.next_slot(18, now).isoformat() == "2026-08-04T18:00:00+00:00"
    assert auto_publish.next_slot(20, now).isoformat() == "2026-08-03T20:00:00+00:00"


def _project(layout):
    return SimpleNamespace(
        focus_x=0.5,
        focus_y=0.5,
        layout=layout,
        trim_start_ms=0,
        overlays=[],
        captions_enabled=False,
        audio={},
        music=None,
    )


def test_render_layouts_build_expected_filter_graphs(tmp_path):
    fill, _ = render.build_filter_graph(
        _project({"mode": "fill"}),
        width=1080,
        height=1920,
        workdir=tmp_path,
        has_audio=False,
        music_index=None,
        image_indices=[],
        source_audio_index=None,
        duration=20,
    )
    assert any("force_original_aspect_ratio=increase" in item for item in fill)

    fit, _ = render.build_filter_graph(
        _project({"mode": "fit"}),
        width=1080,
        height=1920,
        workdir=tmp_path,
        has_audio=False,
        music_index=None,
        image_indices=[],
        source_audio_index=None,
        duration=20,
    )
    assert any("boxblur=24:2" in item for item in fit)
    assert any("force_original_aspect_ratio=decrease" in item for item in fit)

    facecam, _ = render.build_filter_graph(
        _project(
            {
                "mode": "facecam",
                "position": "bottom_left",
                "size": 0.36,
                "camera_x": 0.1,
                "camera_y": 0.2,
                "camera_w": 0.4,
                "camera_h": 0.5,
            }
        ),
        width=1080,
        height=1920,
        workdir=tmp_path,
        has_audio=False,
        music_index=None,
        image_indices=[],
        source_audio_index=None,
        duration=20,
    )
    graph = "\n".join(facecam)
    assert "crop=iw*0.4000:ih*0.5000:iw*0.1000:ih*0.2000" in graph
    assert "overlay=x=(main_w-overlay_w)*0.0400" in graph

    bottom_half, _ = render.build_filter_graph(
        _project({"mode": "facecam", "position": "bottom_half"}),
        width=1080,
        height=1920,
        workdir=tmp_path,
        has_audio=False,
        music_index=None,
        image_indices=[],
        source_audio_index=None,
        duration=20,
    )
    bottom_graph = "\n".join(bottom_half)
    assert "scale=1080:960:force_original_aspect_ratio=increase" in bottom_graph
    assert "overlay=x=(main_w-overlay_w)*0.0000:y=(main_h-overlay_h)*1.0000" in bottom_graph

    gameplay, _ = render.build_filter_graph(
        _project(
            {
                "mode": "gameplay",
                "position": "bottom_right",
                "size": 0.32,
                "camera_x": 0.6,
                "camera_y": 0.55,
                "camera_w": 0.4,
                "camera_h": 0.45,
            }
        ),
        width=1080,
        height=1920,
        workdir=tmp_path,
        has_audio=False,
        music_index=None,
        image_indices=[],
        source_audio_index=None,
        duration=20,
    )
    gameplay_graph = "\n".join(gameplay)
    assert "boxblur" not in gameplay_graph
    assert "crop=iw*0.4000:ih*0.4500:iw*0.6000:ih*0.5500" in gameplay_graph
    assert "overlay=x=(main_w-overlay_w)*0.9600" in gameplay_graph

def test_campaign_overlay_times_are_source_relative_only_when_marked(tmp_path):
    project = _project({"mode": "fill"})
    project.trim_start_ms = 10_000
    filters, _ = render.build_filter_graph(
        project,
        width=1080,
        height=1920,
        workdir=tmp_path,
        has_audio=False,
        music_index=None,
        image_indices=[
            (1, {"source_ms": True, "start_ms": 12_000, "end_ms": 15_000}),
            (1, {"start_ms": 4_000, "end_ms": 8_000}),
        ],
        source_audio_index=None,
        duration=10,
    )
    graph = "\n".join(filters)
    assert "between(t,2.000,5.000)" in graph
    assert "between(t,4.000,8.000)" in graph


def test_text_overlay_times_are_source_relative_only_when_marked():
    relative = captions.build_overlay_ass(
        [{"type": "text", "text": "relative", "start_ms": 500, "end_ms": 1500}],
        clip_start_ms=10_000,
        clip_end_ms=20_000,
        width=1080,
        height=1920,
    )
    assert "relative" in relative
    assert "Dialogue: 0,0:00:00.50,0:00:01.50" in relative
    source = captions.build_overlay_ass(
        [{"type": "text", "text": "source", "start_ms": 12_000, "end_ms": 15_000, "source_ms": True}],
        clip_start_ms=10_000,
        clip_end_ms=20_000,
        width=1080,
        height=1920,
    )
    assert "Dialogue: 0,0:00:02.00,0:00:05.00" in source


def test_heading_can_be_hidden_without_losing_caption_style():
    segments = [
        captions.SegmentData(start_ms=0, end_ms=1200, text="hello world", words=[], confidence=1.0)
    ]
    shown = captions.build_caption_ass(
        segments,
        {"heading": "Big news", "heading_enabled": True, "heading_color": "#ffcc00"},
        clip_start_ms=0,
        clip_end_ms=2000,
        width=1080,
        height=1920,
    )
    assert "Style: Heading" in shown
    assert "Big news" in shown

    hidden = captions.build_caption_ass(
        segments,
        {"heading": "Big news", "heading_enabled": False},
        clip_start_ms=0,
        clip_end_ms=2000,
        width=1080,
        height=1920,
    )
    assert "Style: Heading" not in hidden
    assert "Big news" not in hidden


def test_auto_publish_queues_a_scheduled_job_and_honours_the_score_floor(client, account, uploaded_video):
    with session_scope() as db:
        social = SocialAccount(
            workspace_id=account["workspace_id"],
            platform="youtube",
            account_name="Scheduled channel",
            external_id="scheduled-channel",
            status="connected",
            connected_by=account["user_id"],
        )
        campaign = Campaign(
            workspace_id=account["workspace_id"],
            created_by=account["user_id"],
            name="Scheduled campaign",
            status="active",
            auto_approve=True,
            auto_render=True,
            auto_publish=True,
            auto_publish_min_score=60,
            publish_mode="next_slot",
            publish_hour_utc=18,
            publish_privacy="unlisted",
        )
        db.add_all([social, campaign])
        db.flush()
        campaign.publish_account_ids = [social.id]
        project = EditingProject(
            workspace_id=account["workspace_id"],
            video_id=uploaded_video["id"],
            campaign_id=campaign.id,
            created_by=account["user_id"],
            name="Scheduled project",
            trim_start_ms=0,
            trim_end_ms=5000,
        )
        db.add(project)
        db.flush()
        render_job = RenderJob(
            workspace_id=account["workspace_id"],
            editing_project_id=project.id,
            created_by=account["user_id"],
            status="completed",
        )
        db.add(render_job)
        db.flush()
        export = ExportedVideo(
            workspace_id=account["workspace_id"],
            render_job_id=render_job.id,
            title="Scheduled export",
            filename="scheduled.mp4",
            storage_key="renders/scheduled.mp4",
        )
        db.add(export)
        db.flush()
        qualified = SimpleNamespace(virality_score=80, content={}, title="Qualified", description="")
        pairs = auto_publish.queue_for_export(db, campaign, export, qualified, None, account["user_id"])
        assert len(pairs) == 1
        pipeline_id, job_id = pairs[0]
        assert pipeline_id == ""
        job = db.get(PublishingJob, job_id)
        assert job is not None
        assert job.status == "scheduled"
        assert job.scheduled_for is not None
        assert job.privacy == "unlisted"

        below_floor = SimpleNamespace(virality_score=20, content={}, title="Low", description="")
        assert auto_publish.queue_for_export(
            db, campaign, export, below_floor, None, account["user_id"]
        ) == []


def test_campaign_publish_fields_and_discovery_configuration(client, account):
    headers = account["headers"]
    with session_scope() as db:
        social = SocialAccount(
            workspace_id=account["workspace_id"],
            platform="youtube",
            account_name="Test channel",
            external_id="test-channel",
            status="connected",
            connected_by=account["user_id"],
        )
        db.add(social)
        db.flush()
        social_id = social.id
    response = client.post(
        "/api/campaigns",
        headers=headers,
        json={
            "name": "Auto publish",
            "auto_approve": True,
            "auto_render": True,
            "auto_publish": True,
            "auto_publish_min_score": 70,
            "publish_account_ids": [social_id],
            "publish_mode": "next_slot",
            "publish_hour_utc": 20,
            "publish_privacy": "unlisted",
            "brand": {
                "headline": "Launch week",
                "headline_enabled": True,
                "hashtags": ["#launch", "#summer"],
                "cta": "Follow for more",
                "logo_position": "top_left",
            },
        },
    )
    assert response.status_code == 201, response.text
    campaign = response.json()
    assert campaign["auto_publish"] is True
    assert campaign["publish_mode"] == "next_slot"
    assert campaign["publish_hour_utc"] == 20
    assert campaign["brand"]["hashtags"] == ["#launch", "#summer"]
    assert campaign["brand"]["logo_position"] == "top_left"

    bad = client.patch(
        f"/api/campaigns/{campaign['id']}",
        headers=headers,
        json={"publish_account_ids": ["missing-account"]},
    )
    assert bad.status_code == 400, bad.text

    old_url = settings.campaign_feed_url
    settings.campaign_feed_url = ""
    try:
        discovery = client.get("/api/campaigns/discover", headers=headers)
        assert discovery.status_code == 200, discovery.text
        assert discovery.json()["configured"] is False
        onboard = client.post(
            "/api/campaigns/onboard",
            headers=headers,
            json={"external_id": "summer-2026"},
        )
        assert onboard.status_code == 503, onboard.text
    finally:
        settings.campaign_feed_url = old_url
