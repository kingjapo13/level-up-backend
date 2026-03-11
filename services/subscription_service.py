from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.performance_log import PerformanceLog

FEATURES = {
    "free": {
        "weekly_upload_limit": 1,
        "detailed_feedback": False,
        "advanced_analysis": False,
        "training_plan": False,
        "trend_analysis": False,
        "weekly_reports": False,
    },
    "pro": {
        "weekly_upload_limit": None,
        "detailed_feedback": True,
        "advanced_analysis": False,
        "training_plan": False,
        "trend_analysis": False,
        "weekly_reports": True,
    },
    "elite": {
        "weekly_upload_limit": None,
        "detailed_feedback": True,
        "advanced_analysis": True,
        "training_plan": True,
        "trend_analysis": True,
        "weekly_reports": True,
    },
}


def get_user_tier(user) -> str:
    if user.subscription and user.subscription.is_active:
        return user.subscription.tier
    return "free"


def get_features(tier: str) -> dict:
    return FEATURES.get(tier, FEATURES["free"])


def has_feature(user, feature: str) -> bool:
    return bool(get_features(get_user_tier(user)).get(feature, False))


def enforce_upload_limit(user, db: Session):
    tier = get_user_tier(user)
    limit = FEATURES[tier]["weekly_upload_limit"]

    if limit is None:
        return

    one_week_ago = datetime.utcnow() - timedelta(days=7)
    uploads_this_week = (
        db.query(PerformanceLog)
        .filter(
            PerformanceLog.user_id == user.id,
            PerformanceLog.created_at >= one_week_ago,
        )
        .count()
    )

    if uploads_this_week >= limit:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Your {tier} plan allows {limit} upload(s) per week. "
                "Upgrade to Pro or Elite for unlimited uploads."
            ),
        )