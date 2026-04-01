import logging
import os
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.user import User
from app.models.subscription import Subscription

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


def get_tier_by_price_id(price_id: str) -> str:
    pro_price = os.getenv("STRIPE_PRICE_ID_PRO", "")
    elite_price = os.getenv("STRIPE_PRICE_ID_ELITE", "")
    if price_id == pro_price:
        return "pro"
    if price_id == elite_price:
        return "elite"
    return "pro"


@router.post("/stripe")
async def stripe_webhook(request: Request):
    import stripe
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    try:
        if webhook_secret and sig_header:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        else:
            import json
            event = json.loads(payload)
    except Exception as e:
        logger.error(f"Webhook signature failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    event_type = event.get("type", "")
    logger.info(f"Stripe webhook received: {event_type}")

    db = SessionLocal()
    try:
        if event_type == "checkout.session.completed":
            session = event["data"]["object"]
            customer_email = session.get("customer_details", {}).get("email")
            customer_id = session.get("customer")
            subscription_id = session.get("subscription")
            _handle_new_subscription(db, customer_email, customer_id, subscription_id)

        elif event_type == "customer.subscription.updated":
            sub = event["data"]["object"]
            customer_id = sub.get("customer")
            status = sub.get("status")
            price_id = None
            items = sub.get("items", {}).get("data", [])
            if items:
                price_id = items[0].get("price", {}).get("id")
            _handle_subscription_updated(
                db, customer_id, status, price_id, sub.get("id")
            )

        elif event_type == "customer.subscription.deleted":
            sub = event["data"]["object"]
            customer_id = sub.get("customer")
            _handle_subscription_cancelled(db, customer_id)

        elif event_type == "invoice.payment_failed":
            invoice = event["data"]["object"]
            customer_id = invoice.get("customer")
            customer_email = invoice.get("customer_email")
            logger.warning(
                f"Payment failed for customer {customer_id} ({customer_email})"
            )

    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
    finally:
        db.close()

    return {"status": "ok"}


def _handle_new_subscription(
    db: Session, email: str, customer_id: str, subscription_id: str
):
    if not email:
        logger.warning("No email in checkout session")
        return

    user = db.query(User).filter(User.email == email).first()
    if not user:
        logger.warning(f"No user found for email: {email}")
        return

    import stripe
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

    tier = "pro"
    try:
        if subscription_id:
            sub = stripe.Subscription.retrieve(subscription_id)
            items = sub.get("items", {}).get("data", [])
            if items:
                price_id = items[0].get("price", {}).get("id")
                tier = get_tier_by_price_id(price_id)
    except Exception as e:
        logger.warning(f"Could not retrieve subscription details: {e}")

    subscription = db.query(Subscription).filter(
        Subscription.user_id == user.id
    ).first()

    if subscription:
        subscription.tier = tier
        subscription.stripe_customer_id = customer_id
        subscription.stripe_subscription_id = subscription_id
        subscription.is_active = True
        subscription.updated_at = datetime.utcnow()
    else:
        subscription = Subscription(
            user_id=user.id,
            tier=tier,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            is_active=True,
        )
        db.add(subscription)

    db.commit()
    logger.info(f"User {user.username} upgraded to {tier}")


def _handle_subscription_updated(
    db: Session,
    customer_id: str,
    status: str,
    price_id: str,
    subscription_id: str,
):
    subscription = db.query(Subscription).filter(
        Subscription.stripe_customer_id == customer_id
    ).first()

    if not subscription:
        logger.warning(f"No subscription found for customer: {customer_id}")
        return

    if status == "active" and price_id:
        tier = get_tier_by_price_id(price_id)
        subscription.tier = tier
        subscription.is_active = True
        logger.info(f"Subscription updated to {tier} for customer {customer_id}")
    elif status in ("canceled", "unpaid", "past_due"):
        subscription.tier = "free"
        subscription.is_active = False
        logger.info(f"Subscription deactivated for customer {customer_id}")

    subscription.updated_at = datetime.utcnow()
    db.commit()


def _handle_subscription_cancelled(db: Session, customer_id: str):
    subscription = db.query(Subscription).filter(
        Subscription.stripe_customer_id == customer_id
    ).first()

    if not subscription:
        logger.warning(f"No subscription found for customer: {customer_id}")
        return

    subscription.tier = "free"
    subscription.is_active = False
    subscription.updated_at = datetime.utcnow()
    db.commit()
    logger.info(f"Subscription cancelled for customer {customer_id}")