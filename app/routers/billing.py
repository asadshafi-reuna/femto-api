"""
Purchase flow for unlocking artifacts.

Design note: the browser never tells the API "this is paid". It asks for a
checkout session, the user pays on the provider's page, and the PROVIDER calls
our webhook. Only the webhook marks an order paid and grants the unlock. That
ordering is what makes the paywall real rather than decorative.
"""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..config import settings
from ..db import get_db
from ..deps import current_user
from ..models import CheckoutCreate, OrderPublic

router = APIRouter(prefix="/billing", tags=["billing"])


def _amount_for(kind: str) -> int:
    return {
        "single_unlock": settings.price_single_unlock_cents,
        "credit_pack": settings.price_credit_pack_cents,
        "plan_upgrade": 2900,
    }.get(kind, settings.price_single_unlock_cents)


@router.get("/prices")
async def prices():
    """So the frontend never hardcodes money."""
    return {
        "single_unlock_cents": settings.price_single_unlock_cents,
        "credit_pack_cents": settings.price_credit_pack_cents,
        "credit_pack_size": settings.credit_pack_size,
        "currency": "usd",
    }


@router.post("/checkout", response_model=OrderPublic)
async def create_checkout(body: CheckoutCreate, user: dict = Depends(current_user)):
    """Create a pending order and return a checkout URL.

    Wire Stripe here: create a Checkout Session with metadata
    {order_id, user_id, conversion_id} and return session.url. The order stays
    'pending' until the webhook confirms payment.
    """
    if body.kind == "single_unlock" and not body.conversion_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "conversion_id is required to unlock a single artifact.")

    order = {
        "user_id": user["_id"],
        "kind": body.kind,
        "conversion_id": ObjectId(body.conversion_id) if body.conversion_id else None,
        "quantity": body.quantity,
        "amount_cents": _amount_for(body.kind) * body.quantity,
        "currency": "usd",
        "status": "pending",
        "provider": "stripe",
        "provider_ref": None,
        "created_at": datetime.now(timezone.utc),
        "paid_at": None,
    }
    res = await get_db().orders.insert_one(order)

    checkout_url = None
    if settings.stripe_secret_key:
        # import stripe; session = stripe.checkout.Session.create(...)
        # checkout_url = session.url
        pass

    return OrderPublic(
        id=str(res.inserted_id),
        kind=body.kind,
        conversion_id=body.conversion_id,
        amount_cents=order["amount_cents"],
        currency="usd",
        status="pending",
        checkout_url=checkout_url,
        created_at=order["created_at"],
    )


@router.get("/orders", response_model=list[OrderPublic])
async def my_orders(user: dict = Depends(current_user)):
    cur = get_db().orders.find({"user_id": user["_id"]}).sort("created_at", -1)
    return [
        OrderPublic(
            id=str(d["_id"]),
            kind=d["kind"],
            conversion_id=str(d["conversion_id"]) if d.get("conversion_id") else None,
            amount_cents=d["amount_cents"],
            currency=d.get("currency", "usd"),
            status=d["status"],
            created_at=d["created_at"],
        )
        async for d in cur
    ]


@router.post("/webhook")
async def webhook(request: Request):
    """Called by the payment provider, NOT the browser.

    Verify the signature against STRIPE_WEBHOOK_SECRET before trusting anything —
    without that check anyone could POST here and unlock artifacts for free.
    """
    payload = await request.body()

    if not settings.stripe_webhook_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Billing webhook isn't configured.")

    # stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    # order_id = event.data.object.metadata["order_id"]
    # await _fulfill(order_id)
    return {"received": True}


async def _fulfill(order_id: str) -> None:
    """Mark an order paid and grant what it bought. Idempotent: a provider may
    deliver the same webhook twice, and this must not double-grant."""
    db = get_db()
    order = await db.orders.find_one_and_update(
        {"_id": ObjectId(order_id), "status": "pending"},
        {"$set": {"status": "paid", "paid_at": datetime.now(timezone.utc)}},
    )
    if not order:
        return  # already fulfilled, or unknown

    if order["kind"] == "single_unlock" and order.get("conversion_id"):
        await db.conversions.update_one(
            {"_id": order["conversion_id"], "user_id": order["user_id"]},
            {"$set": {"unlocked": True, "unlock_source": "purchase",
                      "unlock_order_id": order["_id"]}},
        )
    elif order["kind"] == "credit_pack":
        await db.users.update_one(
            {"_id": order["user_id"]},
            {"$inc": {"credits": settings.credit_pack_size * order.get("quantity", 1)}},
        )
    elif order["kind"] == "plan_upgrade":
        await db.users.update_one({"_id": order["user_id"]}, {"$set": {"plan": "pro"}})
