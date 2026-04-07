import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional
from datetime import datetime, timedelta

from app.db.database import get_db
from app.models.user import User
from app.models.performance_log import PerformanceLog
from app.models.subscription import Subscription
from app.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/leaderboard", tags=["Leaderboard"])


def has_social_access(user: User) -> bool:
    """Check if user has Pro or Elite access."""
    if not user.subscription:
        return False
    tier = user.subscription.effective_tier
    return tier in ("pro", "elite", "trial")


def get_user_best_score(db: Session, user_id: int, sport: str) -> Optional[float]:
    """Get user's best score for a sport."""
    result = db.query(func.max(PerformanceLog.score)).filter(
        PerformanceLog.user_id == user_id,
        PerformanceLog.sport == sport,
    ).scalar()
    return result


def get_age_group(age: Optional[int]) -> str:
    """Get age group label."""
    if not age:
        return "unknown"
    if age < 13:
        return "under_13"
    if age <= 17:
        return "13_17"
    if age <= 25:
        return "18_25"
    if age <= 35:
        return "26_35"
    return "35_plus"


def get_age_group_label(group: str) -> str:
    labels = {
        "under_13": "Under 13",
        "13_17": "Ages 13-17",
        "18_25": "Ages 18-25",
        "26_35": "Ages 26-35",
        "35_plus": "Ages 35+",
        "unknown": "All Ages",
    }
    return labels.get(group, "All Ages")


def get_skill_level(score: float) -> str:
    if score >= 90:
        return "elite"
    if score >= 76:
        return "advanced"
    if score >= 51:
        return "intermediate"
    return "beginner"


def get_skill_label(level: str) -> str:
    labels = {
        "elite": "Elite (90+)",
        "advanced": "Advanced (76-90)",
        "intermediate": "Intermediate (51-75)",
        "beginner": "Beginner (0-50)",
    }
    return labels.get(level, level)


@router.get("/percentile")
def get_percentile(
    sport: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get user's percentile rank for a sport."""
    if not has_social_access(user):
        raise HTTPException(
            status_code=403,
            detail="Upgrade to Pro or Elite to see how you compare to others."
        )

    user_best = get_user_best_score(db, user.id, sport)
    if not user_best:
        return {
            "available": False,
            "reason": f"Upload a {sport} video first to see your rank!"
        }

    # Get all users' best scores for this sport
    all_scores = db.query(
        func.max(PerformanceLog.score)
    ).filter(
        PerformanceLog.sport == sport,
    ).group_by(PerformanceLog.user_id).all()

    all_scores_flat = [s[0] for s in all_scores if s[0] is not None]

    if len(all_scores_flat) < 2:
        return {
            "available": False,
            "reason": "Not enough players yet to compare — check back soon!"
        }

    scores_below = sum(1 for s in all_scores_flat if s < user_best)
    percentile = round((scores_below / len(all_scores_flat)) * 100)

    skill_level = get_skill_level(user_best)

    if percentile >= 90:
        message = f"You're in the top {100 - percentile}% of {sport} players! 🔥"
    elif percentile >= 75:
        message = f"You're better than {percentile}% of {sport} players! 💪"
    elif percentile >= 50:
        message = f"You're above average for {sport}! Keep pushing! 📈"
    else:
        message = f"Keep training — you're improving every session! 🎯"

    return {
        "available": True,
        "sport": sport,
        "user_best_score": round(user_best),
        "percentile": percentile,
        "total_players": len(all_scores_flat),
        "skill_level": skill_level,
        "skill_label": get_skill_label(skill_level),
        "message": message,
        "rank": len(all_scores_flat) - scores_below,
    }


@router.get("/global")
def get_global_leaderboard(
    sport: str = "basketball",
    category: str = "overall",
    age_group: Optional[str] = None,
    skill_level: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get leaderboard for a sport filtered by category."""
    if not has_social_access(user):
        raise HTTPException(
            status_code=403,
            detail="Upgrade to Pro or Elite to access leaderboards."
        )

    # Get best score per user for this sport
    subquery = db.query(
        PerformanceLog.user_id,
        func.max(PerformanceLog.score).label("best_score"),
        func.count(PerformanceLog.id).label("total_sessions"),
    ).filter(
        PerformanceLog.sport == sport,
        PerformanceLog.score.isnot(None),
    ).group_by(PerformanceLog.user_id).subquery()

    # Join with users
    results = db.query(
        User.id,
        User.username,
        User.age,
        User.location,
        subquery.c.best_score,
        subquery.c.total_sessions,
    ).join(
        subquery, User.id == subquery.c.user_id
    ).filter(
        subquery.c.best_score.isnot(None)
    )

    # Filter by age group
    if category == "age" and age_group and age_group != "all":
        if age_group == "under_13":
            results = results.filter(User.age < 13)
        elif age_group == "13_17":
            results = results.filter(User.age >= 13, User.age <= 17)
        elif age_group == "18_25":
            results = results.filter(User.age >= 18, User.age <= 25)
        elif age_group == "26_35":
            results = results.filter(User.age >= 26, User.age <= 35)
        elif age_group == "35_plus":
            results = results.filter(User.age > 35)

    # Filter by skill level
    if category == "skill" and skill_level:
        if skill_level == "elite":
            results = results.filter(subquery.c.best_score >= 90)
        elif skill_level == "advanced":
            results = results.filter(
                subquery.c.best_score >= 76,
                subquery.c.best_score < 90
            )
        elif skill_level == "intermediate":
            results = results.filter(
                subquery.c.best_score >= 51,
                subquery.c.best_score < 76
            )
        elif skill_level == "beginner":
            results = results.filter(subquery.c.best_score < 51)

    results = results.order_by(desc(subquery.c.best_score)).limit(limit).all()

    # Find current user's rank
    user_rank = None
    user_entry = None
    for i, r in enumerate(results):
        if r[0] == user.id:
            user_rank = i + 1
            user_entry = r
            break

    leaderboard = []
    for i, r in enumerate(results):
        user_id, username, age, location, best_score, sessions = r
        skill = get_skill_level(best_score)
        entry = {
            "rank": i + 1,
            "user_id": user_id,
            "username": username,
            "age": age,
            "location": location or "Unknown",
            "best_score": round(best_score),
            "total_sessions": sessions,
            "skill_level": skill,
            "skill_label": get_skill_label(skill),
            "is_current_user": user_id == user.id,
            "medal": (
                "🥇" if i == 0 else
                "🥈" if i == 1 else
                "🥉" if i == 2 else None
            ),
        }
        leaderboard.append(entry)

    return {
        "sport": sport,
        "category": category,
        "leaderboard": leaderboard,
        "user_rank": user_rank,
        "total_players": len(results),
        "filters": {
            "age_group": age_group,
            "skill_level": skill_level,
        }
    }