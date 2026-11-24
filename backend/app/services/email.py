"""Transactional email delivery.

SMTP is optional. When it is not configured, messages (including the action
link) are written to the server log so a local install can still verify
accounts and reset passwords. Nothing is ever reported as delivered unless the
SMTP server accepted it.
"""
from __future__ import annotations

import html
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from ..config import settings

logger = logging.getLogger("fireclip.email")


def action_url(path: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/{path.lstrip('/')}"


def _message(to: str, subject: str, text: str, html_body: str | None = None) -> EmailMessage:
    message = EmailMessage()
    message["From"] = formataddr((settings.mail_from_name, settings.mail_from))
    message["To"] = to
    message["Subject"] = " ".join(subject.splitlines()).strip()[:200]
    message.set_content(text)
    if html_body:
        message.add_alternative(html_body, subtype="html")
    return message


def _html(title: str, body: str, cta_label: str | None = None, cta_url: str | None = None) -> str:
    button = ""
    if cta_label and cta_url:
        button = (
            f'<p style="margin:28px 0"><a href="{html.escape(cta_url)}" '
            'style="background:#ff6a1f;color:#160b04;text-decoration:none;font-weight:700;'
            'padding:12px 22px;border-radius:10px;display:inline-block">'
            f"{html.escape(cta_label)}</a></p>"
            f'<p style="font-size:12px;color:#667085;word-break:break-all">{html.escape(cta_url)}</p>'
        )
    return (
        '<div style="background:#0b0b0e;padding:32px 16px;font-family:Inter,Arial,sans-serif">'
        '<div style="max-width:560px;margin:0 auto;background:#141419;border:1px solid #26262e;'
        'border-radius:16px;padding:32px;color:#e8e8ee">'
        '<p style="font-size:13px;letter-spacing:.12em;color:#ff6a1f;font-weight:700">FIRECLIP</p>'
        f'<h1 style="font-size:22px;margin:12px 0 8px">{html.escape(title)}</h1>'
        f'<div style="font-size:14px;line-height:1.7;color:#b9b9c4">{body}</div>'
        f"{button}"
        '<p style="font-size:11px;color:#667085;margin-top:28px">If you did not request this, you can ignore the email.</p>'
        "</div></div>"
    )


def send_email(to: str, subject: str, text: str, html_body: str | None = None) -> bool:
    """Deliver an email. Returns True only when SMTP accepted the message."""
    if not settings.email_configured:
        logger.warning("Email not configured; %s for %s: %s", subject, to, text)
        return False
    message = _message(to, subject, text, html_body)
    try:
        if settings.smtp_ssl:
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout
            )
        else:
            server = smtplib.SMTP(
                settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout
            )
        with server:
            server.ehlo()
            if settings.smtp_starttls and not settings.smtp_ssl:
                server.starttls()
                server.ehlo()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
        logger.info("Sent '%s' to %s", subject, to)
        return True
    except Exception:
        logger.exception("Could not send '%s' to %s", subject, to)
        return False


def send_verification(to: str, name: str, token: str) -> bool:
    url = action_url(f"verify-email?token={token}")
    text = (
        f"Hi {name or 'there'},\n\nConfirm your FireClip email address:\n{url}\n\n"
        f"The link expires in {settings.email_verification_hours} hours."
    )
    body = (
        "<p>Confirm this address to secure your account and receive processing "
        "notifications.</p>"
    )
    return send_email(to, "Confirm your FireClip email", text, _html("Confirm your email", body, "Confirm email", url))


def send_password_reset(to: str, name: str, token: str) -> bool:
    url = action_url(f"reset-password?token={token}")
    text = (
        f"Hi {name or 'there'},\n\nReset your FireClip password:\n{url}\n\n"
        f"The link expires in {settings.password_reset_minutes} minutes. "
        "If you did not ask for this, ignore the email."
    )
    body = (
        "<p>Use the button below to choose a new password. The link can be used "
        "once and expires shortly.</p>"
    )
    return send_email(to, "Reset your FireClip password", text, _html("Reset your password", body, "Choose a new password", url))


def send_workspace_invite(to: str, inviter: str, workspace: str, role: str, token: str) -> bool:
    url = action_url(f"invite/{token}")
    text = (
        f"{inviter or 'A teammate'} invited you to the {workspace} workspace on FireClip "
        f"as {role}.\n\nAccept the invitation:\n{url}\n\n"
        f"The invitation expires in {settings.invite_expiry_days} days."
    )
    body = (
        f"<p><strong>{html.escape(inviter or 'A teammate')}</strong> invited you to "
        f"<strong>{html.escape(workspace)}</strong> as <strong>{html.escape(role)}</strong>.</p>"
    )
    return send_email(
        to,
        f"Join {workspace} on FireClip",
        text,
        _html(f"You are invited to {workspace}", body, "Accept invitation", url),
    )


def send_password_changed(to: str, name: str) -> bool:
    text = f"Hi {name or 'there'},\n\nYour FireClip password was changed. If this was not you, reset it now."
    return send_email(to, "Your FireClip password changed", text)
