import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime

from app.db.database import get_db
from app.models.user import User
from app.models.performance_log import PerformanceLog
from app.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recruiting", tags=["Recruiting"])


@router.get("/report-data")
def get_report_data(
    sport: str = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all data needed to generate a recruiting PDF report."""
    try:
        query = db.query(PerformanceLog).filter(
            PerformanceLog.user_id == user.id
        )
        if sport:
            query = query.filter(PerformanceLog.sport == sport)

        logs = query.order_by(PerformanceLog.created_at.asc()).all()

        if not logs:
            raise HTTPException(
                status_code=404,
                detail="No sessions found. Upload training videos first."
            )

        scores = [l.score for l in logs if l.score]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0
        best_score = round(max(scores), 1) if scores else 0
        latest_score = round(logs[-1].score, 1) if logs[-1].score else 0

        # Improvement
        first_score = scores[0] if scores else 0
        improvement = round(latest_score - first_score, 1)

        # Sports breakdown
        sports_data = {}
        for log in logs:
            if log.sport not in sports_data:
                sports_data[log.sport] = []
            if log.score:
                sports_data[log.sport].append(log.score)

        sports_summary = {}
        for sport_name, sport_scores in sports_data.items():
            sports_summary[sport_name] = {
                "sessions": len(sport_scores),
                "best": round(max(sport_scores), 1),
                "avg": round(sum(sport_scores) / len(sport_scores), 1),
            }

        # Common form issues
        all_issues = []
        for log in logs:
            if log.metrics and isinstance(log.metrics, dict):
                issues = log.metrics.get("form_issues", [])
                all_issues.extend(issues)

        issue_counts = {}
        for issue in all_issues:
            key = issue[:50]
            issue_counts[key] = issue_counts.get(key, 0) + 1

        top_issues = sorted(
            issue_counts.items(), key=lambda x: x[1], reverse=True
        )[:3]

        # Strengths — sessions with no issues
        clean_sessions = sum(
            1 for log in logs
            if log.metrics and not log.metrics.get("form_issues")
        )

        # Progress over time
        progress = []
        for log in logs[-20:]:
            progress.append({
                "date": log.created_at.strftime("%b %d"),
                "score": round(log.score, 1) if log.score else 0,
                "sport": log.sport,
            })

        # Streak
        streak = 0
        today = datetime.utcnow().date()
        dates = sorted(set(
            l.created_at.date() for l in logs if l.created_at
        ), reverse=True)
        for i, date in enumerate(dates):
            from datetime import timedelta
            expected = today - timedelta(days=i)
            if date == expected:
                streak += 1
            else:
                break

        return {
            "athlete_name": user.username,
            "generated_date": datetime.utcnow().strftime("%B %d, %Y"),
            "total_sessions": len(logs),
            "avg_score": avg_score,
            "best_score": best_score,
            "latest_score": latest_score,
            "improvement": improvement,
            "streak": streak,
            "clean_sessions": clean_sessions,
            "sports_summary": sports_summary,
            "top_issues": [{"issue": i[0], "count": i[1]} for i in top_issues],
            "progress": progress,
            "sport_filter": sport,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report data error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))