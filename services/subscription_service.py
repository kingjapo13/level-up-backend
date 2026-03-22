from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.performance_log import PerformanceLog

FEATURES = {
    "trial": {
        "daily_upload_limit": None,
        "detailed_feedback": True,
        "advanced_analysis": False,
        "training_plan": False,
        "trend_analysis": False,
        "weekly_reports": True,
    },
    "free": {
        "daily_upload_limit": 1,
        "detailed_feedback": False,
        "advanced_analysis": False,
        "training_plan": False,
        "trend_analysis": False,
        "weekly_reports": False,
    },
    "pro": {
        "daily_upload_limit": None,
        "detailed_feedback": True,
        "advanced_analysis": False,
        "training_plan": False,
        "trend_analysis": False,
        "weekly_reports": True,
    },
    "elite": {
        "daily_upload_limit": None,
        "detailed_feedback": True,
        "advanced_analysis": True,
        "training_plan": True,
        "trend_analysis": True,
        "weekly_reports": True,
    },
    "expired": {
        "daily_upload_limit": 0,
        "detailed_feedback": False,
        "advanced_analysis": False,
        "training_plan": False,
        "trend_analysis": False,
        "weekly_reports": False,
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
            detail="Your 7-day free trial has expired. Please upgrade to Pro or Elite to continue.",
        )

    limit = get_features(tier).get("daily_upload_limit")

    if limit is None:
        return

    if limit == 0:
        raise HTTPException(
            status_code=403,
            detail="Your free trial has expired. Upgrade to continue analyzing videos.",
        )

    today_start = datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    uploads_today = (
        db.query(PerformanceLog)
        .filter(
            PerformanceLog.user_id == user.id,
            PerformanceLog.created_at >= today_start,
        )
        .count()
    )

    if uploads_today >= limit:
        raise HTTPException(
            status_code=403,
            detail=(
                f"You have reached your daily limit of {limit} upload(s). "
                "Upgrade to Pro or Elite for unlimited uploads."
            ),
        )