from typing import Dict, Any

FEATURES: Dict[str, Dict[str, Any]] = {
  "trial": {
        "max_uploads_per_week": -1,
        "max_athletes": 5,
        "weekly_reports": True,
        "detailed_feedback": True,
        "custom_training": False,
        "rep_counting": True,
        "advanced_breakdown": False,
        "historical_months": 6,
        "video_comparison": False,
        "priority_support": False,
        "early_access": False,
    },
    "expired": {
        "max_uploads_per_week": 0,
        "max_athletes": 0,
        "weekly_reports": False,
        "detailed_feedback": False,
        "custom_training": False,
        "rep_counting": False,
        "advanced_breakdown": False,
        "historical_months": 0,
        "video_comparison": False,
        "priority_support": False,
        "early_access": False,
    },
    "pro": {
        "daily_upload_limit": -1,
        "max_athletes": 5,
        "weekly_reports": True,
        "detailed_feedback": True,
        "custom_training": True,
        "rep_counting": True,
        "advanced_breakdown": False,
        "historical_months": 6,
        "video_comparison": False,
        "priority_support": False,
        "early_access": False,
    },
    "elite": {
        "daily_upload_limit": -1,
        "max_athletes": -1,
        "weekly_reports": True,
        "detailed_feedback": True,
        "custom_training": True,
        "rep_counting": True,
        "advanced_breakdown": True,
        "historical_months": 24,
        "video_comparison": True,
        "priority_support": True,
        "early_access": True,
    },
}


def get_features(tier: str) -> Dict[str, Any]:
    return FEATURES.get(tier, FEATURES["free"])


def has_feature(tier: str, feature: str) -> bool:
    return bool(get_features(tier).get(feature, False))