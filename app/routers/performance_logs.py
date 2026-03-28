from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.models.performance_log import PerformanceLog
from app.security import get_current_user

router = APIRouter(prefix="/performance-logs", tags=["Performance Logs"])


@router.get("/")
def get_logs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    logs = (
        db.query(PerformanceLog)
        .filter(PerformanceLog.user_id == user.id)
        .order_by(PerformanceLog.created_at.desc())
        .all()
    )
    return [_format_log(log) for log in logs]


@router.get("/{log_id}")
def get_log(
    log_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    log = (
        db.query(PerformanceLog)
        .filter(
            PerformanceLog.id == log_id,
            PerformanceLog.user_id == user.id,
        )
        .first()
    )
    if not log:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Session not found")
    return _format_log(log, full=True)


def _format_log(log: PerformanceLog, full: bool = False) -> dict:
    metrics = log.metrics or {}
    result = {
        "id": log.id,
        "sport": log.sport,
        "score": log.score,
        "reps": log.reps,
        "date": log.created_at,
        "form_issues": metrics.get("form_issues", []),
        "coaching_tips": metrics.get("coaching_tips", []),
    }
    if full:
        result.update({
            "summary": metrics.get("summary", ""),
            "gpt_feedback": metrics.get("gpt_feedback", ""),
            "improvement": metrics.get("improvement", ""),
            "training_plan": metrics.get("training_plan", None),
            "annotated_frames": metrics.get("annotated_frames", []),
        })
    return result