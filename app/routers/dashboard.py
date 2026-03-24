from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.db.database import get_db
from app.models.user import User
from app.models.performance_log import PerformanceLog
from app.security import get_current_user
from app.config.subscription_features import get_features
from services.ai_report_service import generate_weekly_report
from services.dashboard_service import generate_training_plan
from utils.helpers import safe_average, get_tier

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def calculate_streak(logs):
    if not logs:
        return 0
    dates = sorted(set(
        log.created_at.date() for log in logs
    ), reverse=True)
    streak = 0
    today = datetime.utcnow().date()
    for i, date in enumerate(dates):
        expected = today - timedelta(days=i)
        if date == expected:
            streak += 1
        else:
            break
    return streak


def get_personal_bests(logs):
    bests = {}
    for log in logs:
        if log.sport not in bests or (log.score or 0) > bests[log.sport]:
            bests[log.sport] = log.score or 0
    return bests


def get_weekly_challenge(logs):
    now = datetime.utcnow()
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0)
    weekly_logs = [l for l in logs if l.created_at >= week_start]
    target_score = 80
    best_this_week = max((l.score or 0) for l in weekly_logs) if weekly_logs else 0
    completed = best_this_week >= target_score
    return {
        "title": f"Score {target_score}+ this week",
        "description": f"Upload a video and score {target_score} or higher",
        "target": target_score,
        "best_this_week": round(best_this_week),
        "completed": completed,
        "sessions_this_week": len(weekly_logs),
    }


def check_personal_best(logs, latest_log):
    if not latest_log or not latest_log.score:
        return None
    sport_logs = [l for l in logs if l.sport == latest_log.sport and l.id != latest_log.id]
    if not sport_logs:
        return None
    prev_best = max((l.score or 0) for l in sport_logs)
    if latest_log.score > prev_best:
        return {
            "is_personal_best": True,
            "sport": latest_log.sport,
            "new_best": round(latest_log.score),
            "previous_best": round(prev_best),
            "improvement": round(latest_log.score - prev_best, 1),
        }
    return None


@router.get("/")
def get_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tier = get_tier(user)

    logs = (
        db.query(PerformanceLog)
        .filter(PerformanceLog.user_id == user.id)
        .order_by(PerformanceLog.created_at.asc())
        .all()
    )

    scores = [l.score for l in logs if l.score is not None]

    progress = [
        {
            "date": log.created_at,
            "sport": log.sport,
            "score": log.score,
            "reps": log.reps,
        }
        for log in logs
    ]

    streak = calculate_streak(logs)
    personal_bests = get_personal_bests(logs)
    weekly_challenge = get_weekly_challenge(logs)

    latest_log = logs[-1] if logs else None
    personal_best_alert = check_personal_best(logs, latest_log)

    is_trial = False
    trial_expired = False
    trial_days = 0

    if user.subscription:
        is_trial = user.subscription.is_trial
        trial_expired = user.subscription.trial_expired
        trial_days = user.subscription.trial_days_remaining

    return {
        "username": user.username,
        "tier": tier,
        "is_trial": is_trial,
        "trial_expired": trial_expired,
        "trial_days_remaining": trial_days,
        "total_sessions": len(logs),
        "average_score": safe_average(scores),
        "streak": streak,
        "personal_bests": personal_bests,
        "weekly_challenge": weekly_challenge,
        "personal_best_alert": personal_best_alert,
        "progress": progress,
    }


@router.get("/weekly-report")
def weekly_report(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tier = get_tier(user)
    if not get_features(tier).get("weekly_reports"):
        raise HTTPException(
            status_code=403,
            detail="Weekly reports require a Pro or Elite subscription.",
        )
    return generate_weekly_report(user, db)


@router.get("/training-plan")
def training_plan(
    sport: str = "general",
    user: User = Depends(get_current_user),
):
    tier = get_tier(user)
    if not get_features(tier).get("training_plan"):
        raise HTTPException(
            status_code=403,
            detail="Training plans require an Elite subscription.",
        )
    return {"plan": generate_training_plan(sport=sport)}