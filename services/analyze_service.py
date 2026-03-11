import os
import uuid
import shutil
import logging

from sqlalchemy.orm import Session

from app.models.performance_log import PerformanceLog
from app.models.user import User
from services.subscription_service import enforce_upload_limit, has_feature
from app.gpt_coach import generate_gpt_feedback
from services.push_service import send_push_notification

logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def analyze_video(file, sport: str, db: Session, user: User) -> dict:
    enforce_upload_limit(user, db)

    ext = os.path.splitext(file.filename)[-1] or ".mp4"
    filename = f"{UPLOAD_DIR}/{uuid.uuid4()}{ext}"
    with open(filename, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    logger.info(f"User {user.id} uploaded video for sport={sport}: {filename}")

    last_log = (
        db.query(PerformanceLog)
        .filter(PerformanceLog.user_id == user.id, PerformanceLog.sport == sport)
        .order_by(PerformanceLog.created_at.desc())
        .first()
    )
    previous_score = int(last_log.score) if last_log and last_log.score else None

    from analysis.process_video import analyze_video as run_analysis
    result = run_analysis(filename, sport=sport, previous_score=previous_score)

    if "error" in result:
        return result

    if has_feature(user, "detailed_feedback"):
        gpt = generate_gpt_feedback(
            metrics=result,
            sport=sport,
            personality=user.personality_mode or "supportive",
        )
        result["gpt_feedback"] = gpt

    log = PerformanceLog(
        user_id=user.id,
        sport=sport,
        score=result.get("score"),
        reps=result.get("reps_completed"),
        video_path=filename,
        metrics={
            "form_issues": result.get("form_issues", []),
            "coaching_tips": result.get("coaching_tips", []),
        },
    )
    db.add(log)
    db.commit()

    _notify_complete(user)

    return result


def _notify_complete(user: User):
    if not user.device_token:
        return
    try:
        send_push_notification(
            token=user.device_token,
            title="Analysis Ready 🏆",
            body="Your LevelUp AI coaching feedback is ready to view.",
        )
    except Exception as e:
        logger.warning(f"Push notification failed for user {user.id}: {e}")