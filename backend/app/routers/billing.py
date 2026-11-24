"""Billing endpoints: plans, Stripe checkout, portal, invoices and webhooks."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from ..deps import RequestContext, get_context, record_audit
from ..models import BillingInvoice
from ..schemas import CheckoutRequest
from ..services import billing

logger = logging.getLogger("fireclip.billing")

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/plans")
def plans(ctx: RequestContext = Depends(get_context)):
    price_configured = {
        f"{plan['id']}:{interval}": bool(billing.price_id(plan["id"], interval))
        for plan in billing.PLANS
        for interval in ("month", "year")
    }
    return {
        "plans": billing.PLANS,
        "provider": billing.provider_status(),
        "prices": price_configured,
        "current": {
            "plan": ctx.workspace.plan,
            "status": ctx.workspace.plan_status,
            "interval": ctx.workspace.plan_interval,
            "renews_at": ctx.workspace.plan_renews_at,
        },
    }


@router.post("/checkout")
def checkout(payload: CheckoutRequest, ctx: RequestContext = Depends(get_context)):
    ctx.require("admin")
    try:
        url = billing.create_checkout(
            ctx.db, ctx.workspace, ctx.user.email, payload.plan, payload.interval
        )
    except billing.BillingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    record_audit(
        ctx.db,
        "billing.checkout",
        workspace_id=ctx.workspace.id,
        user_id=ctx.user.id,
        target_type="workspace",
        target_id=ctx.workspace.id,
        ip_address=ctx.ip_address,
        meta={"plan": payload.plan, "interval": payload.interval},
    )
    ctx.db.commit()
    return {"url": url}


@router.post("/portal")
def portal(ctx: RequestContext = Depends(get_context)):
    ctx.require("admin")
    try:
        url = billing.create_portal(ctx.db, ctx.workspace, ctx.user.email)
    except billing.BillingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return {"url": url}


@router.get("/invoices")
def invoices(ctx: RequestContext = Depends(get_context)):
    rows = ctx.db.scalars(
        select(BillingInvoice)
        .where(BillingInvoice.workspace_id == ctx.workspace.id)
        .order_by(BillingInvoice.created_at.desc())
        .limit(50)
    )
    return [
        {
            "id": row.id,
            "number": row.number,
            "status": row.status,
            "amount_cents": row.amount_cents,
            "currency": row.currency,
            "hosted_url": row.hosted_url,
            "pdf_url": row.pdf_url,
            "period_start": row.period_start,
            "period_end": row.period_end,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.post("/webhook")
async def webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = billing.verify_webhook(payload, signature)
    except billing.BillingError as exc:
        logger.warning("Rejected Stripe webhook: %s", exc.message)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    from ..database import session_scope

    try:
        with session_scope() as db:
            billing.process_event(db, event)
    except Exception:
        logger.exception("Stripe webhook processing failed")
        # A 500 makes Stripe retry, which is what we want for transient failures.
        raise HTTPException(status_code=500, detail="Could not process webhook")
    return {"received": True, "type": event.get("type", "")}
