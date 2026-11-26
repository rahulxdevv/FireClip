"""Billing plans and an optional Stripe integration.

The product is fully usable without a payment provider. When Stripe keys and
price IDs are configured, checkout, the customer portal, invoices and webhook
synchronisation become available; otherwise the API reports that honestly
instead of pretending a checkout happened.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..models import BillingEvent, BillingInvoice, CandidateClip, Workspace

logger = logging.getLogger("fireclip.billing")


class BillingError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


DEFAULT_PLAN = "starter"

PLANS: list[dict] = [
    {
        "id": "starter",
        "name": "Starter",
        "tagline": "For creators shipping a few short clips a week.",
        "monthly": 19,
        "yearly": 190,
        "clips": 300,
        "minutes": 300,
        "features": ["300 clips / month", "300 render minutes", "Every editing tool included", "No per-seat limits"],
    },
    {
        "id": "studio",
        "name": "Studio",
        "tagline": "A full content engine for a small team.",
        "monthly": 49,
        "yearly": 490,
        "clips": 500,
        "minutes": 600,
        "features": ["500 clips / month", "600 render minutes", "Every editing tool included", "No per-seat limits"],
    },
    {
        "id": "agency",
        "name": "Agency",
        "tagline": "Many brands, one self-hosted workspace.",
        "monthly": 149,
        "yearly": 1490,
        "clips": 2500,
        "minutes": 3000,
        "features": ["2,500 clips / month", "3,000 render minutes", "Every editing tool included", "No per-seat limits"],
    },
]
PLAN_INDEX = {plan["id"]: plan for plan in PLANS}


def plan_limits(plan: str) -> tuple[int, int]:
    entry = PLAN_INDEX.get(plan, PLAN_INDEX[DEFAULT_PLAN])
    return int(entry["clips"]), int(entry["minutes"])


def apply_plan(workspace: Workspace, plan: str) -> None:
    if plan not in PLAN_INDEX:
        plan = DEFAULT_PLAN
    clips, minutes = plan_limits(plan)
    workspace.plan = plan
    workspace.monthly_clip_limit = clips
    workspace.monthly_render_minutes = minutes


def clips_used_this_month(db: Session, workspace_id: str) -> int:
    """Count clips created since the first day of the current UTC month."""
    start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return int(
        db.scalar(
            select(func.count())
            .select_from(CandidateClip)
            .where(CandidateClip.workspace_id == workspace_id, CandidateClip.created_at >= start)
        )
        or 0
    )


def price_id(plan: str, interval: str) -> str:
    return settings.price_map.get(f"{plan}:{interval}", "")


def plan_for_price(price: str) -> str | None:
    for key, value in settings.price_map.items():
        if value and value == price:
            return key.split(":", 1)[0]
    return None


def _flatten(data: dict, prefix: str = "") -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for key, value in data.items():
        name = f"{prefix}[{key}]" if prefix else key
        if value is None:
            continue
        if isinstance(value, dict):
            pairs.extend(_flatten(value, name))
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                item_name = f"{name}[{index}]"
                if isinstance(item, dict):
                    pairs.extend(_flatten(item, item_name))
                else:
                    pairs.append((item_name, str(item)))
        elif isinstance(value, bool):
            pairs.append((name, "true" if value else "false"))
        else:
            pairs.append((name, str(value)))
    return pairs


def stripe_request(method: str, path: str, data: dict | None = None) -> dict:
    if not settings.stripe_secret_key:
        raise BillingError("Stripe is not configured on this instance", 503)
    url = f"{settings.stripe_api_base.rstrip('/')}{path}"
    headers = {"Authorization": f"Bearer {settings.stripe_secret_key}"}
    try:
        with httpx.Client(timeout=25) as client:
            response = client.request(
                method, url, headers=headers, data=_flatten(data or {}) if data else None
            )
    except httpx.HTTPError as exc:
        logger.exception("Stripe request failed")
        raise BillingError(f"Could not reach Stripe: {exc}", 502) from exc
    if response.status_code >= 400:
        try:
            detail = response.json().get("error", {}).get("message", "")
        except Exception:
            detail = response.text[:300]
        raise BillingError(detail or "Stripe rejected the request", 502)
    return response.json()


def provider_status() -> dict:
    keys_ready = bool(settings.stripe_secret_key and any(settings.price_map.values()))
    configured = bool(keys_ready and settings.stripe_webhook_secret)
    if configured:
        message = "Stripe is connected. Plan changes are handled by Stripe Checkout and webhooks."
    elif keys_ready:
        message = (
            "Stripe keys are present, but STRIPE_WEBHOOK_SECRET is missing. Checkout stays "
            "disabled until webhooks can confirm payment."
        )
    else:
        message = (
            "No payment provider is connected. Plan limits are enforced locally and "
            "workspaces stay on their current plan; add Stripe keys to enable checkout."
        )
    return {
        "available": configured,
        "provider": "stripe" if configured else None,
        "publishable_key": None,
        "message": message,
    }


def ensure_customer(db: Session, workspace: Workspace, email: str) -> str:
    if workspace.stripe_customer_id:
        return workspace.stripe_customer_id
    customer = stripe_request(
        "POST",
        "/v1/customers",
        {"email": email, "name": workspace.name, "metadata": {"workspace_id": workspace.id}},
    )
    workspace.stripe_customer_id = customer.get("id", "")
    db.commit()
    return workspace.stripe_customer_id or ""


def create_checkout(
    db: Session, workspace: Workspace, email: str, plan: str, interval: str
) -> str:
    if plan not in PLAN_INDEX:
        raise BillingError("Choose a plan to continue")
    if interval not in {"month", "year"}:
        raise BillingError("Billing interval must be month or year")
    if not settings.stripe_webhook_secret:
        raise BillingError(
            "Stripe webhooks are not configured, so a payment could not be fulfilled. "
            "Set STRIPE_WEBHOOK_SECRET first.",
            503,
        )
    price = price_id(plan, interval)
    if not price:
        raise BillingError(
            f"No Stripe price is configured for the {plan} plan ({interval}ly). "
            "Set STRIPE_PRICE_* environment variables.",
            503,
        )
    customer = ensure_customer(db, workspace, email)
    base = settings.frontend_url.rstrip("/")
    session = stripe_request(
        "POST",
        "/v1/checkout/sessions",
        {
            "mode": "subscription",
            "customer": customer,
            "client_reference_id": workspace.id,
            "line_items": [{"price": price, "quantity": 1}],
            "allow_promotion_codes": True,
            "billing_address_collection": "auto",
            "success_url": f"{base}/billing?checkout=success",
            "cancel_url": f"{base}/billing?checkout=cancelled",
            "subscription_data": {"metadata": {"workspace_id": workspace.id, "plan": plan}},
        },
    )
    url = session.get("url")
    if not url:
        raise BillingError("Stripe did not return a checkout URL", 502)
    return url


def create_portal(db: Session, workspace: Workspace, email: str) -> str:
    customer = ensure_customer(db, workspace, email)
    payload: dict = {
        "customer": customer,
        "return_url": f"{settings.frontend_url.rstrip('/')}/billing",
    }
    if settings.stripe_portal_configuration:
        payload["configuration"] = settings.stripe_portal_configuration
    session = stripe_request("POST", "/v1/billing_portal/sessions", payload)
    url = session.get("url")
    if not url:
        raise BillingError("Stripe did not return a portal URL", 502)
    return url


def verify_webhook(payload: bytes, signature_header: str, tolerance: int = 300) -> dict:
    if not settings.stripe_webhook_secret:
        raise BillingError("Stripe webhooks are not configured", 503)
    if not signature_header:
        raise BillingError("Missing Stripe-Signature header")
    parts: dict[str, list[str]] = {}
    for piece in signature_header.split(","):
        if "=" not in piece:
            continue
        key, value = piece.split("=", 1)
        parts.setdefault(key.strip(), []).append(value.strip())
    try:
        timestamp = int(parts.get("t", ["0"])[0])
    except ValueError as exc:
        raise BillingError("Malformed Stripe-Signature header") from exc
    if abs(time.time() - timestamp) > tolerance:
        raise BillingError("Stripe webhook timestamp is outside the tolerance window")
    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(
        settings.stripe_webhook_secret.encode("utf-8"), signed, hashlib.sha256
    ).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in parts.get("v1", [])):
        raise BillingError("Stripe webhook signature did not match")
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BillingError("Stripe webhook body was not valid JSON") from exc


def _timestamp(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def workspace_for_customer(db: Session, customer_id: str | None) -> Workspace | None:
    if not customer_id:
        return None
    return db.scalar(select(Workspace).where(Workspace.stripe_customer_id == customer_id))


def sync_subscription(db: Session, workspace: Workspace, subscription: dict) -> None:
    workspace.stripe_subscription_id = subscription.get("id", workspace.stripe_subscription_id)
    workspace.plan_status = subscription.get("status", workspace.plan_status)
    workspace.plan_renews_at = _timestamp(subscription.get("current_period_end"))
    items = (subscription.get("items") or {}).get("data") or []
    price = ""
    if items:
        price = ((items[0] or {}).get("price") or {}).get("id", "")
    plan = plan_for_price(price)
    if subscription.get("status") in {"canceled", "unpaid", "incomplete_expired"}:
        # A finished subscription drops to the entry plan.
        apply_plan(workspace, DEFAULT_PLAN)
    elif plan:
        apply_plan(workspace, plan)
    db.commit()


def upsert_invoice(db: Session, workspace: Workspace, invoice: dict) -> None:
    external = str(invoice.get("id") or "")
    if not external:
        return
    row = db.scalar(select(BillingInvoice).where(BillingInvoice.external_id == external))
    if not row:
        row = BillingInvoice(workspace_id=workspace.id, external_id=external)
        db.add(row)
    row.number = invoice.get("number") or ""
    row.status = invoice.get("status") or "open"
    row.amount_cents = int(invoice.get("amount_paid") or invoice.get("amount_due") or 0)
    row.currency = invoice.get("currency") or "usd"
    row.hosted_url = invoice.get("hosted_invoice_url") or ""
    row.pdf_url = invoice.get("invoice_pdf") or ""
    row.period_start = _timestamp(invoice.get("period_start"))
    row.period_end = _timestamp(invoice.get("period_end"))
    db.commit()


def process_event(db: Session, event: dict) -> None:
    event_id = str(event.get("id") or "")
    if event_id:
        seen = db.scalar(select(BillingEvent).where(BillingEvent.external_id == event_id))
        if seen:
            return
    event_type = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}
    if event_type == "checkout.session.completed":
        workspace = db.get(Workspace, obj.get("client_reference_id") or "")
        if not workspace:
            workspace = workspace_for_customer(db, obj.get("customer"))
        if workspace:
            workspace.stripe_customer_id = obj.get("customer") or workspace.stripe_customer_id
            workspace.stripe_subscription_id = obj.get("subscription") or workspace.stripe_subscription_id
            workspace.plan_status = "active"
            db.commit()
    elif event_type.startswith("customer.subscription."):
        workspace = db.get(Workspace, ((obj.get("metadata") or {}).get("workspace_id") or ""))
        if not workspace:
            workspace = workspace_for_customer(db, obj.get("customer"))
        if workspace:
            sync_subscription(db, workspace, obj)
    elif event_type.startswith("invoice."):
        workspace = db.get(Workspace, ((obj.get("subscription_details") or {}).get("metadata") or {}).get("workspace_id", ""))
        if not workspace:
            workspace = workspace_for_customer(db, obj.get("customer"))
        if workspace:
            upsert_invoice(db, workspace, obj)
            if event_type == "invoice.payment_failed":
                workspace.plan_status = "past_due"
                db.commit()
    if event_id:
        # Record the event only after it has been applied so a transient failure
        # is retried by Stripe instead of being permanently marked as seen.
        db.add(BillingEvent(external_id=event_id, event_type=event_type))
        try:
            db.commit()
        except IntegrityError:
            # A concurrent delivery already recorded this event.
            db.rollback()
