import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.db.database import get_db
from app.models.user import User
from app.models.performance_log import PerformanceLog
from app.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def calculate_streak(logs):
    if not logs:
        return 0
    try:
        dates = sorted(set(
            log.created_at.date() for log in logs
            if log.created_at
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
    except Exception:
        return 0


def get_personal_bests(logs):
    bests = {}
    try:
        for log in logs:
            if log.sport and (log.sport not in bests or (log.score or 0) > bests[log.sport]):
                bests[log.sport] = log.score or 0
    except Exception:
        pass
    return bests


def get_weekly_challenge(logs):
    try:
        now = datetime.utcnow()
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0)
        weekly_logs = [l for l in logs if l.created_at and l.created_at >= week_start]
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
    except Exception:
        return {
            "title": "Score 80+ this week",
            "description": "Upload a video and score 80 or higher",
            "target": 80,
            "best_this_week": 0,
            "completed": False,
            "sessions_this_week": 0,
        }


def check_personal_best(logs, latest_log):
    try:
        if not latest_log or not latest_log.score:
            return None
        sport_logs = [
            l for l in logs
            if l.sport == latest_log.sport and l.id != latest_log.id
        ]
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
    except Exception:
        pass
    return None


def get_tier(user: User) -> str:
    try:
        if user.subscription:
            return user.subscription.effective_tier
    except Exception:
        pass
    return "free"


def safe_average(scores):
    if not scores:
        return None
    try:
        return round(sum(scores) / len(scores), 1)
    except Exception:
        return None


@router.get("/")
def get_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        tier = get_tier(user)

        logs = (
            db.query(PerformanceLog)
            .filter(PerformanceLog.user_id == user.id)
            .order_by(PerformanceLog.created_at.asc())
            .all()
        )

        scores = [l.score for l in logs if l.score is not None]

        progress = []
        for log in logs:
            try:
                progress.append({
                    "id": log.id,
                    "date": log.created_at,
                    "sport": log.sport,
                    "score": log.score,
                    "reps": log.reps,
                })
            except Exception:
                pass

        streak = calculate_streak(logs)
        personal_bests = get_personal_bests(logs)
        weekly_challenge = get_weekly_challenge(logs)
        latest_log = logs[-1] if logs else None
        personal_best_alert = check_personal_best(logs, latest_log)

        is_trial = False
        trial_expired = False
        trial_days = 0

        try:
            if user.subscription:
                is_trial = getattr(user.subscription, 'is_trial', False)
                trial_expired = getattr(user.subscription, 'trial_expired', False)
                trial_days = getattr(user.subscription, 'trial_days_remaining', 0)
        except Exception as e:
            logger.warning(f"Subscription access error: {e}")

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

    except Exception as e:
        logger.error(f"Dashboard error for user {user.id}: {e}", exc_info=True)
        return {
            "username": getattr(user, 'username', 'Athlete'),
            "tier": "free",
            "is_trial": False,
            "trial_expired": False,
            "trial_days_remaining": None,
            "streak": 0,
            "total_sessions": 0,
            "average_score": None,
            "progress": [],
            "personal_bests": {},
            "personal_best_alert": None,
            "weekly_challenge": {
                "title": "Score 80+ this week",
                "description": "Upload a video and score 80 or higher",
                "target": 80,
                "best_this_week": 0,
                "completed": False,
                "sessions_this_week": 0,
            },
        }


@router.get("/weekly-report")
def weekly_report(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        from app.config.subscription_features import get_features
        tier = get_tier(user)
        if not get_features(tier).get("weekly_reports"):
            raise HTTPException(
                status_code=403,
                detail="Weekly reports require a Pro or Elite subscription.",
            )
        from services.ai_report_service import generate_weekly_report
        return generate_weekly_report(user, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Weekly report error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not generate weekly report")


@router.get("/training-plan")
def training_plan(
    sport: str = "general",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        from app.config.subscription_features import get_features
        from services.dashboard_service import generate_training_plan
        tier = get_tier(user)
        if not get_features(tier).get("training_plan"):
            raise HTTPException(
                status_code=403,
                detail="Training plans require an Elite subscription.",
            )
        return {"plan": generate_training_plan(sport=sport)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Training plan error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not generate training plan")