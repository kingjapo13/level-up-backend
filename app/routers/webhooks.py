import os
import logging
import stripe

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.subscription import Subscription

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


@router.post("/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "customer.subscription.updated":
        _handle_subscription_update(data, db)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(data, db)

    return {"status": "ok"}


def _handle_subscription_update(data: dict, db: Session):
    stripe_sub_id = data.get("id")
    sub = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == stripe_sub_id
    ).first()
    if not sub:
        return
    price_id = data["items"]["data"][0]["price"]["id"]
    tier_map = {
        os.getenv("STRIPE_PRICE_ID_PRO"): "pro",
        os.getenv("STRIPE_PRICE_ID_ELITE"): "elite",
    }
    sub.tier = tier_map.get(price_id, "free")
    db.commit()


def _handle_subscription_deleted(data: dict, db: Session):
    stripe_sub_id = data.get("id")
    sub = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == stripe_sub_id
    ).first()
    if sub:
        sub.tier = "free"
        db.commit()