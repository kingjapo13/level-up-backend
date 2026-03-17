from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.performance_log import PerformanceLog

FEATURES = {
    "free": {
        "daily_upload_limit": 1,
        "weekly_upload_limit": None,
        "detailed_feedback": False,
        "advanced_analysis": False,
        "training_plan": False,
        "trend_analysis": False,
        "weekly_reports": False,
    },
    "pro": {
        "daily_upload_limit": None,
        "weekly_upload_limit": None,
        "detailed_feedback": True,
        "advanced_analysis": False,
        "training_plan": False,
        "trend_analysis": False,
        "weekly_reports": True,
    },
    "elite": {
        "daily_upload_limit": None,
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
    """
    Free tier: 1 upload per day
    Pro/Elite: unlimited
    """
    tier = get_user_tier(user)
    features = FEATURES[tier]

    # Check daily limit for free users
    daily_limit = features.get("daily_upload_limit")
    if daily_limit is not None:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        uploads_today = (
            db.query(PerformanceLog)
            .filter(
                PerformanceLog.user_id == user.id,
                PerformanceLog.created_at >= today_start,
            )
            .count()
        )
        if uploads_today >= daily_limit:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"You have reached your daily limit of {daily_limit} "
                    f"video upload(s) on the free plan. "
                    "Upgrade to Pro or Elite for unlimited uploads."
                ),
            )