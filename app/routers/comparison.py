import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta

from app.db.database import get_db
from app.models.user import User
from app.models.performance_log import PerformanceLog
from app.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/comparison", tags=["Comparison"])


@router.get("/")
def get_comparison(
    sport: Optional[str] = None,
    period: str = "month",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(PerformanceLog).filter(
        PerformanceLog.user_id == user.id
    )
    if sport:
        query = query.filter(PerformanceLog.sport == sport)

    logs = query.order_by(PerformanceLog.created_at.asc()).all()

    if len(logs) < 2:
        return {
            "available": False,
            "reason": "Upload at least 2 sessions to see your before vs after!"
        }

    last_log = logs[-1]

    # Find best "before" log based on period
    if period == "week":
        cutoff = last_log.created_at - timedelta(days=7)
    elif period == "month":
        cutoff = last_log.created_at - timedelta(days=30)
    else:
        cutoff = last_log.created_at - timedelta(days=3650)

    older_logs = [l for l in logs if l.created_at <= cutoff]
    first_log = older_logs[0] if older_logs else logs[0]

    if first_log.id == last_log.id:
        first_log = logs[0]

    first_metrics = first_log.metrics or {}
    last_metrics = last_log.metrics or {}

    first_issues = first_metrics.get("form_issues", [])
    last_issues = last_metrics.get("form_issues", [])
    first_frames = first_metrics.get("annotated_frames", [])
    last_frames = last_metrics.get("annotated_frames", [])

    score_change = (last_log.score or 0) - (first_log.score or 0)
    issue_change = len(first_issues) - len(last_issues)
    days_apart = (last_log.created_at - first_log.created_at).days

    if score_change >= 20:
        message = f"🔥 Incredible improvement! +{score_change:.0f} points in {days_apart} days!"
    elif score_change >= 10:
        message = f"💪 Great progress! +{score_change:.0f} points since you started!"
    elif score_change >= 5:
        message = f"📈 Good progress! Up {score_change:.0f} points — keep going!"
    elif score_change >= 1:
        message = f"✅ Improving! +{score_change:.0f} points since your first session"
    elif score_change == 0:
        message = "Consistency is key — keep uploading to see improvement!"
    else:
        message = "Keep practicing — results come with consistency!"

    period_label = (
        f"{days_apart} days"
        if days_apart < 30
        else f"{days_apart // 30} month{'s' if days_apart // 30 != 1 else ''}"
    )

    return {
        "available": True,
        "period_label": period_label,
        "sport": first_log.sport,
        "message": message,
        "score_change": round(score_change),
        "issue_change": issue_change,
        "before": {
            "date": first_log.created_at,
            "score": round(first_log.score or 0),
            "reps": first_log.reps or 0,
            "form_issues": first_issues,
            "tips_count": len(first_metrics.get("coaching_tips", [])),
            "frame": first_frames[0] if first_frames else None,
            "summary": first_metrics.get("summary", ""),
        },
        "after": {
            "date": last_log.created_at,
            "score": round(last_log.score or 0),
            "reps": last_log.reps or 0,
            "form_issues": last_issues,
            "tips_count": len(last_metrics.get("coaching_tips", [])),
            "frame": last_frames[0] if last_frames else None,
            "summary": last_metrics.get("summary", ""),
        },
    }