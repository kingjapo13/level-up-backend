from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.performance_log import PerformanceLog

FEATURES = {
    "trial": {
        "monthly_upload_limit": 10,
        "detailed_feedback": True,
        "athlete_matching": False,
        "training_plan": True,
        "weekly_reports": True,
        "gpt_feedback": True,
    },
    "free": {
        "monthly_upload_limit": 0,
        "detailed_feedback": False,
        "athlete_matching": False,
        "training_plan": False,
        "weekly_reports": False,
        "gpt_feedback": False,
    },
    "pro": {
        "monthly_upload_limit": 1,
        "detailed_feedback": True,
        "athlete_matching": False,
        "training_plan": False,
        "weekly_reports": True,
        "gpt_feedback": True,
    },
    "elite": {
        "monthly_upload_limit": 100,
        "detailed_feedback": True,
        "athlete_matching": True,
        "training_plan": True,
        "weekly_reports": True,
        "gpt_feedback": True,
    },
    "expired": {
        "monthly_upload_limit": 0,
        "detailed_feedback": False,
        "athlete_matching": False,
        "training_plan": False,
        "weekly_reports": False,
        "gpt_feedback": False,
    },
}


def get_user_tier(user) -> str:
    if not user.subscription:
        return "free"
    return user.subscription.effective_tier


def get_features(tier: str) -> dict:
    return FEATURES.get(tier, FEATURES["free"])


def has_feature(user, feature: str) -> bool:
    tier = get_user_tier(user)
    return bool(get_features(tier).get(feature, False))


def enforce_upload_limit(user, db: Session):
    tier = get_user_tier(user)

    if tier == "expired":
        raise HTTPException(
            status_code=403,
            detail="Your 7-day free trial has expired. Please upgrade to continue.",
        )

    if tier == "free":
        raise HTTPException(
            status_code=403,
            detail="Please start your free trial or upgrade to upload videos.",
        )

    limit = get_features(tier).get("monthly_upload_limit", 0)

    if limit == 0:
        raise HTTPException(
            status_code=403,
            detail="Your plan does not include video uploads. Please upgrade.",
        )

    # Count uploads this month
    month_start = datetime.utcnow().replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    uploads_this_month = (
        db.query(PerformanceLog)
        .filter(
            PerformanceLog.user_id == user.id,
            PerformanceLog.created_at >= month_start,
        )
        .count()
    )

    if uploads_this_month >= limit:
        raise HTTPException(
            status_code=403,
            detail=(
                f"You have used all {limit} upload(s) for this month. "
                f"{'Upgrade to Elite for 100 uploads/month.' if tier == 'pro' else 'Your limit resets next month.'}"
            ),
        )