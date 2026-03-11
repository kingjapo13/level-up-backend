from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.models.performance_log import PerformanceLog
from app.security import get_current_user
from app.config.subscription_features import get_features
from services.ai_report_service import generate_weekly_report
from services.dashboard_service import generate_training_plan
from utils.helpers import safe_average, get_tier

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


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
    return {
        "username": user.username,
        "tier": tier,
        "total_sessions": len(logs),
        "average_score": safe_average(scores),
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