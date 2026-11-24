"""Social platform integrations (OAuth + publishing).

Real API calls only. If credentials or platform permissions are missing the
call fails loudly and the publishing job records the error - FireClip never
reports a fake success. YouTube, Facebook and Instagram paths are implemented
against official APIs; TikTok's content posting API is scaffolded and requires
an approved developer app (see KNOWN LIMITATIONS in the README).
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AnalyticsRecord, ExportedVideo, PublishingJob, SocialAccount
from ..security import create_token, decrypt_secret, decode_token, encrypt_secret
from ..storage import get_storage
from .webhooks import emit as emit_webhook

logger = logging.getLogger("fireclip.publishing")

PLATFORM_LABELS = {
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "facebook": "Facebook",
}
SCOPES = {
    "youtube": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly",
    "facebook": "pages_manage_posts,pages_read_engagement,pages_show_list",
    "instagram": "pages_show_list,instagram_basic,instagram_content_publish,instagram_manage_insights",
    "tiktok": "video.publish,user.info.basic",
}


class PublishError(RuntimeError):
    pass


def _creds(platform: str) -> tuple[str, str] | None:
    mapping = {
        "youtube": (settings.google_client_id, settings.google_client_secret),
        "facebook": (settings.facebook_client_id, settings.facebook_client_secret),
        "instagram": (settings.instagram_client_id or settings.facebook_client_id,
                      settings.instagram_client_secret or settings.facebook_client_secret),
        "tiktok": (settings.tiktok_client_key, settings.tiktok_client_secret),
    }
    pair = mapping.get(platform)
    if not pair or not pair[0] or not pair[1]:
        return None
    return pair


def redirect_uri(platform: str) -> str:
    return f"{settings.backend_public_url.rstrip('/')}/api/publishing/callback/{platform}"


def authorize_url(platform: str, workspace_id: str, user_id: str) -> tuple[bool, str | None, str]:
    creds = _creds(platform)
    if not creds:
        return (
            False,
            None,
            f"{PLATFORM_LABELS[platform]} is not configured. Set the platform OAuth client ID and "
            "secret on the server, then add the callback URL in the developer console.",
        )
    verifier = secrets.token_urlsafe(48) if platform == "tiktok" else ""
    state = create_token(
        user_id,
        "oauth",
        timedelta(minutes=15),
        {"ws": workspace_id, "platform": platform, "verifier": verifier},
    )
    client_id, _secret = creds
    if platform == "youtube":
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri(platform),
            "response_type": "code",
            "scope": SCOPES[platform],
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return True, f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}", ""
    if platform in {"facebook", "instagram"}:
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri(platform),
            "state": state,
            "scope": SCOPES[platform],
            "response_type": "code",
        }
        return True, f"https://www.facebook.com/v19.0/dialog/oauth?{urlencode(params)}", ""
    if platform == "tiktok":
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        params = {
            "client_key": client_id,
            "scope": SCOPES[platform],
            "response_type": "code",
            "redirect_uri": redirect_uri(platform),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return True, f"https://www.tiktok.com/v2/auth/authorize/?{urlencode(params)}", ""
    return False, None, "Unsupported platform"


def decode_state(state: str, platform: str) -> dict:
    payload = decode_token(state, "oauth")
    if not payload or payload.get("platform") != platform:
        raise PublishError("OAuth state is invalid or expired. Start the connection again.")
    return payload


def exchange_code(platform: str, code: str, state_payload: dict) -> dict:
    """Exchange an authorization code and return account fields to persist."""
    creds = _creds(platform)
    if not creds:
        raise PublishError("OAuth credentials are not configured for this platform")
    client_id, client_secret = creds
    try:
        if platform == "youtube":
            response = httpx.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri(platform),
                    "grant_type": "authorization_code",
                },
                timeout=45,
            )
            _raise_for_oauth(response, platform)
            tokens = response.json()
            channel = httpx.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "snippet", "mine": "true"},
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                timeout=45,
            )
            info = channel.json() if channel.status_code < 400 else {}
            item = (info.get("items") or [{}])[0]
            return {
                "access_token": tokens.get("access_token", ""),
                "refresh_token": tokens.get("refresh_token", ""),
                "expires_in": tokens.get("expires_in", 0),
                "account_name": item.get("snippet", {}).get("title") or "YouTube channel",
                "external_id": item.get("id", ""),
                "scopes": tokens.get("scope", SCOPES[platform]),
            }
        if platform in {"facebook", "instagram"}:
            token_response = httpx.get(
                "https://graph.facebook.com/v19.0/oauth/access_token",
                params={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri(platform),
                    "code": code,
                },
                timeout=45,
            )
            _raise_for_oauth(token_response, platform)
            short = token_response.json()
            long_response = httpx.get(
                "https://graph.facebook.com/v19.0/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "fb_exchange_token": short.get("access_token", ""),
                },
                timeout=45,
            )
            token_data = long_response.json() if long_response.status_code < 400 else short
            user_token = token_data.get("access_token", "")
            pages = httpx.get(
                "https://graph.facebook.com/v19.0/me/accounts",
                params={
                    "fields": "id,name,access_token,instagram_business_account{id,username}",
                    "access_token": user_token,
                },
                timeout=45,
            )
            _raise_for_oauth(pages, platform)
            page_items = pages.json().get("data") or []
            if not page_items:
                raise PublishError(
                    "This account manages no Facebook pages. A page is required to publish videos."
                )
            page = page_items[0]
            ig = page.get("instagram_business_account") or {}
            if platform == "instagram" and not ig.get("id"):
                raise PublishError("No Instagram Business account is linked to this Facebook page.")
            return {
                "access_token": page.get("access_token") or user_token,
                "refresh_token": user_token,
                "expires_in": int(token_data.get("expires_in") or 0),
                "account_name": (ig.get("username") if platform == "instagram" else page.get("name"))
                or PLATFORM_LABELS[platform],
                "external_id": (ig.get("id") if platform == "instagram" else page.get("id")) or "",
                "scopes": SCOPES[platform],
            }
        if platform == "tiktok":
            response = httpx.post(
                "https://open.tiktokapis.com/v2/oauth/token/",
                data={
                    "client_key": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri(platform),
                    "code_verifier": state_payload.get("verifier", ""),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=45,
            )
            _raise_for_oauth(response, platform)
            tokens = response.json()
            user = httpx.get(
                "https://open.tiktokapis.com/v2/user/info/",
                params={"fields": "display_name,username"},
                headers={"Authorization": f"Bearer {tokens.get('access_token', '')}"},
                timeout=45,
            )
            info = (user.json().get("data") or {}).get("user") or {} if user.status_code < 400 else {}
            return {
                "access_token": tokens.get("access_token", ""),
                "refresh_token": tokens.get("refresh_token", ""),
                "expires_in": int(tokens.get("expires_in") or 0),
                "account_name": info.get("display_name") or info.get("username") or "TikTok account",
                "external_id": tokens.get("open_id", ""),
                "scopes": tokens.get("scope", SCOPES[platform]),
            }
    except httpx.HTTPError as exc:
        raise PublishError(f"{PLATFORM_LABELS[platform]} OAuth request failed: {exc}") from exc
    raise PublishError("Unsupported platform")


def _raise_for_oauth(response: httpx.Response, platform: str) -> None:
    if response.status_code >= 400:
        raise PublishError(
            f"{PLATFORM_LABELS[platform]} OAuth error {response.status_code}: {response.text[:400]}"
        )


def _token(account: SocialAccount) -> str:
    token = decrypt_secret(account.access_token_encrypted)
    if not token:
        raise PublishError("Stored access token could not be decrypted. Reconnect the account.")
    return token


def _maybe_refresh(db: Session, account: SocialAccount) -> str:
    token = _token(account)
    expires = account.token_expires_at
    if not expires:
        return token
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires - datetime.now(timezone.utc) > timedelta(minutes=2):
        return token
    refresh = decrypt_secret(account.refresh_token_encrypted)
    creds = _creds(account.platform)
    if not refresh or not creds:
        raise PublishError("The access token has expired and cannot be refreshed. Reconnect the account.")
    client_id, client_secret = creds
    try:
        if account.platform == "youtube":
            response = httpx.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh,
                    "grant_type": "refresh_token",
                },
                timeout=45,
            )
        elif account.platform == "tiktok":
            response = httpx.post(
                "https://open.tiktokapis.com/v2/oauth/token/",
                data={
                    "client_key": client_id,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                },
                timeout=45,
            )
        else:
            response = httpx.get(
                "https://graph.facebook.com/v19.0/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "fb_exchange_token": refresh,
                },
                timeout=45,
            )
    except httpx.HTTPError as exc:
        raise PublishError(f"Token refresh failed: {exc}") from exc
    if response.status_code >= 400:
        raise PublishError(f"Token refresh failed {response.status_code}: {response.text[:300]}")
    data = response.json()
    new_token = data.get("access_token")
    if not new_token:
        raise PublishError("Token refresh returned no access token")
    account.access_token_encrypted = encrypt_secret(new_token)
    if data.get("refresh_token"):
        account.refresh_token_encrypted = encrypt_secret(data["refresh_token"])
    if data.get("expires_in"):
        account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(data["expires_in"]))
    db.commit()
    return new_token


def _export_path(export: ExportedVideo):
    storage = get_storage()
    return storage, storage.temp_copy(export.storage_key)


def _public_export_url(export: ExportedVideo) -> str:
    if settings.storage_backend == "s3" and settings.media_public_base_url:
        return f"{settings.media_public_base_url.rstrip('/')}/{export.storage_key}"
    if settings.media_public_base_url:
        return f"{settings.media_public_base_url.rstrip('/')}/{export.storage_key}"
    raise PublishError(
        "Instagram publishing needs a publicly reachable video URL. Configure S3 storage and "
        "MEDIA_PUBLIC_BASE_URL, or publish this export to another platform."
    )


def _publish_youtube(db: Session, account: SocialAccount, export: ExportedVideo, job: PublishingJob) -> dict:
    token = _maybe_refresh(db, account)
    title = (job.title or export.title or "FireClip clip")[:100]
    description = (job.caption or "")[:4900]
    if job.hashtags:
        description = f"{description}\n\n{job.hashtags}"[:4900]
    metadata = {
        "snippet": {"title": title, "description": description, "categoryId": "22"},
        "status": {
            "privacyStatus": job.privacy if job.privacy in {"public", "unlisted", "private"} else "private",
            "selfDeclaredMadeForKids": False,
        },
    }
    try:
        init = httpx.post(
            "https://www.googleapis.com/upload/youtube/v3/videos",
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/mp4",
            },
            content=json.dumps(metadata),
            timeout=60,
        )
        if init.status_code >= 400:
            raise PublishError(f"YouTube upload init failed {init.status_code}: {init.text[:400]}")
        upload_url = init.headers.get("location")
        if not upload_url:
            raise PublishError("YouTube did not return a resumable upload URL")
        storage, context = _export_path(export)
        try:
            with context as path:
                with open(path, "rb") as handle:
                    upload = httpx.put(
                        upload_url,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "video/mp4",
                            "Content-Length": str(path.stat().st_size),
                        },
                        content=handle.read(),
                        timeout=600,
                    )
        finally:
            pass
        if upload.status_code >= 400:
            raise PublishError(f"YouTube upload failed {upload.status_code}: {upload.text[:400]}")
        data = upload.json()
        video_id = data.get("id", "")
        return {
            "external_post_id": video_id,
            "external_url": f"https://www.youtube.com/watch?v={video_id}" if video_id else None,
        }
    except httpx.HTTPError as exc:
        raise PublishError(f"YouTube request failed: {exc}") from exc


def _publish_facebook(db: Session, account: SocialAccount, export: ExportedVideo, job: PublishingJob) -> dict:
    token = _maybe_refresh(db, account)
    caption = job.caption or export.title
    if job.hashtags:
        caption = f"{caption}\n\n{job.hashtags}"
    storage, context = _export_path(export)
    try:
        with context as path:
            with open(path, "rb") as handle:
                response = httpx.post(
                    f"https://graph-video.facebook.com/v19.0/{account.external_id}/videos",
                    data={"description": caption, "access_token": token},
                    files={"source": (export.filename or "clip.mp4", handle, "video/mp4")},
                    timeout=600,
                )
    except httpx.HTTPError as exc:
        raise PublishError(f"Facebook upload failed: {exc}") from exc
    if response.status_code >= 400:
        raise PublishError(f"Facebook upload failed {response.status_code}: {response.text[:400]}")
    data = response.json()
    post_id = data.get("id", "")
    return {
        "external_post_id": post_id,
        "external_url": f"https://www.facebook.com/{post_id}" if post_id else None,
    }


def _publish_instagram(db: Session, account: SocialAccount, export: ExportedVideo, job: PublishingJob) -> dict:
    token = _maybe_refresh(db, account)
    public_url = _public_export_url(export)
    caption = job.caption or export.title
    if job.hashtags:
        caption = f"{caption}\n\n{job.hashtags}"
    try:
        create = httpx.post(
            f"https://graph.facebook.com/v19.0/{account.external_id}/media",
            data={
                "media_type": "REELS",
                "video_url": public_url,
                "caption": caption[:2200],
                "share_to_feed": "true",
                "access_token": token,
            },
            timeout=120,
        )
        if create.status_code >= 400:
            raise PublishError(f"Instagram container failed {create.status_code}: {create.text[:400]}")
        container_id = create.json().get("id")
        if not container_id:
            raise PublishError("Instagram did not return a container id")
        for _attempt in range(30):
            status = httpx.get(
                f"https://graph.facebook.com/v19.0/{container_id}",
                params={"fields": "status_code", "access_token": token},
                timeout=45,
            )
            state = (status.json() or {}).get("status_code", "")
            if state == "FINISHED":
                break
            if state == "ERROR":
                raise PublishError("Instagram rejected the video container. Check the file format.")
            import time

            time.sleep(5)
        else:
            raise PublishError("Instagram did not finish processing the video in time")
        publish = httpx.post(
            f"https://graph.facebook.com/v19.0/{account.external_id}/media_publish",
            data={"creation_id": container_id, "access_token": token},
            timeout=120,
        )
        if publish.status_code >= 400:
            raise PublishError(f"Instagram publish failed {publish.status_code}: {publish.text[:400]}")
        media_id = publish.json().get("id", "")
        return {
            "external_post_id": media_id,
            "external_url": f"https://www.instagram.com/reel/{media_id}" if media_id else None,
        }
    except httpx.HTTPError as exc:
        raise PublishError(f"Instagram request failed: {exc}") from exc


def _publish_tiktok(db: Session, account: SocialAccount, export: ExportedVideo, job: PublishingJob) -> dict:
    token = _maybe_refresh(db, account)
    storage, context = _export_path(export)
    with context as path:
        size = path.stat().st_size
        if size > 64 * 1024 * 1024:
            raise PublishError("TikTok single-chunk upload supports files up to 64MB in this build")
        try:
            init = httpx.post(
                "https://open.tiktokapis.com/v2/post/publish/video/init/",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={
                    "post_info": {
                        "title": (job.caption or export.title)[:2200],
                        "privacy_level": "PUBLIC_TO_EVERYONE" if job.privacy == "public" else "SELF_ONLY",
                        "disable_duet": False,
                        "disable_comment": False,
                        "disable_stitch": False,
                    },
                    "source_info": {
                        "source": "FILE_UPLOAD",
                        "video_size": size,
                        "chunk_size": size,
                        "total_chunk_count": 1,
                    },
                },
                timeout=60,
            )
            if init.status_code >= 400:
                raise PublishError(f"TikTok init failed {init.status_code}: {init.text[:400]}")
            data = init.json().get("data") or {}
            upload_url = data.get("upload_url")
            publish_id = data.get("publish_id")
            if not upload_url:
                raise PublishError("TikTok did not return an upload URL")
            with open(path, "rb") as handle:
                upload = httpx.put(
                    upload_url,
                    headers={
                        "Content-Type": "video/mp4",
                        "Content-Range": f"bytes 0-{size - 1}/{size}",
                        "Content-Length": str(size),
                    },
                    content=handle.read(),
                    timeout=600,
                )
            if upload.status_code >= 400:
                raise PublishError(f"TikTok upload failed {upload.status_code}: {upload.text[:300]}")
        except httpx.HTTPError as exc:
            raise PublishError(f"TikTok request failed: {exc}") from exc
    return {
        "external_post_id": publish_id,
        "external_url": None,
    }


PUBLISHERS = {
    "youtube": _publish_youtube,
    "facebook": _publish_facebook,
    "instagram": _publish_instagram,
    "tiktok": _publish_tiktok,
}


def execute_publish(job_id: str) -> dict:
    from ..database import session_scope
    from ..deps import notify, record_audit

    with session_scope() as db:
        job = db.get(PublishingJob, job_id)
        if not job:
            raise PublishError("Publishing job not found")
        if job.status == "published":
            return {"status": "published"}
        account = db.get(SocialAccount, job.social_account_id)
        export = db.get(ExportedVideo, job.exported_video_id)
        if not account or not export:
            raise PublishError("Missing account or export for this publishing job")
        job.status = "publishing"
        job.attempts += 1
        job.error_message = None
        db.commit()
        job_id_value = job.id
        platform = job.platform
        workspace_id = job.workspace_id
        created_by = job.created_by

    try:
        with session_scope() as db:
            job = db.get(PublishingJob, job_id_value)
            account = db.get(SocialAccount, job.social_account_id)
            export = db.get(ExportedVideo, job.exported_video_id)
            publisher = PUBLISHERS.get(platform)
            if not publisher:
                raise PublishError(f"Publishing to {platform} is not supported")
            result = publisher(db, account, export, job)
        with session_scope() as db:
            job = db.get(PublishingJob, job_id_value)
            job.status = "published"
            job.external_post_id = result.get("external_post_id") or job.external_post_id
            job.external_url = result.get("external_url") or job.external_url
            job.published_at = datetime.now(timezone.utc)
            job.error_message = None
            notify(
                db,
                workspace_id,
                created_by,
                f"Published to {PLATFORM_LABELS.get(platform, platform)}",
                job.external_url or "Publishing completed.",
                "success",
            )
            record_audit(
                db, "publish.completed", workspace_id=workspace_id, user_id=created_by,
                target_type="publishing_job", target_id=job_id_value,
                meta={"platform": platform, "post_id": result.get("external_post_id")},
            )
            emit_webhook(
                db,
                workspace_id,
                "clip.published",
                {
                    "publishing_job_id": job_id_value,
                    "platform": platform,
                    "external_url": job.external_url,
                    "external_post_id": job.external_post_id,
                },
            )
        return {"status": "published", **result}
    except Exception as exc:
        with session_scope() as db:
            job = db.get(PublishingJob, job_id_value)
            if job:
                job.status = "failed"
                job.error_message = str(exc)[:2000]
            account = db.get(SocialAccount, job.social_account_id) if job else None
            if account:
                account.last_error = str(exc)[:1000]
            notify(
                db,
                workspace_id,
                created_by,
                f"Publishing failed on {PLATFORM_LABELS.get(platform, platform)}",
                str(exc)[:900],
                "error",
            )
            record_audit(
                db, "publish.failed", workspace_id=workspace_id, user_id=created_by,
                target_type="publishing_job", target_id=job_id_value,
                meta={"platform": platform, "error": str(exc)[:500]},
            )
        raise


def fetch_metrics(db: Session, account: SocialAccount, job: PublishingJob) -> dict | None:
    token = _maybe_refresh(db, account)
    if not job.external_post_id:
        return None
    try:
        if account.platform == "youtube":
            response = httpx.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "statistics", "id": job.external_post_id},
                headers={"Authorization": f"Bearer {token}"},
                timeout=45,
            )
            if response.status_code >= 400:
                raise PublishError(f"YouTube analytics error {response.status_code}: {response.text[:300]}")
            items = response.json().get("items") or []
            if not items:
                return None
            stats = items[0].get("statistics", {})
            return {
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
                "shares": 0,
            }
        if account.platform == "facebook":
            response = httpx.get(
                f"https://graph.facebook.com/v19.0/{job.external_post_id}",
                params={
                    "fields": "views,likes.summary(true),comments.summary(true),shares",
                    "access_token": token,
                },
                timeout=45,
            )
            if response.status_code >= 400:
                raise PublishError(f"Facebook analytics error {response.status_code}: {response.text[:300]}")
            data = response.json()
            return {
                "views": int((data.get("views") or 0)),
                "likes": int(((data.get("likes") or {}).get("summary") or {}).get("total_count") or 0),
                "comments": int(((data.get("comments") or {}).get("summary") or {}).get("total_count") or 0),
                "shares": int((data.get("shares") or {}).get("count") or 0),
            }
        if account.platform == "instagram":
            response = httpx.get(
                f"https://graph.facebook.com/v19.0/{job.external_post_id}",
                params={"fields": "like_count,comments_count", "access_token": token},
                timeout=45,
            )
            if response.status_code >= 400:
                raise PublishError(f"Instagram analytics error {response.status_code}: {response.text[:300]}")
            data = response.json()
            return {
                "views": 0,
                "likes": int(data.get("like_count") or 0),
                "comments": int(data.get("comments_count") or 0),
                "shares": 0,
            }
        if account.platform == "tiktok":
            raise PublishError(
                "TikTok metrics require the video.list scope and an approved app; not available here."
            )
    except httpx.HTTPError as exc:
        raise PublishError(f"Analytics request failed: {exc}") from exc
    return None
