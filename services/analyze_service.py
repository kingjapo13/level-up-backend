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
    # 1. Check upload limit
    enforce_upload_limit(user, db)

    # 2. Save file safely
    ext = os.path.splitext(file.filename)[-1].lower() or ".mp4"
    filename = f"{UPLOAD_DIR}/{uuid.uuid4()}{ext}"

    try:
        with open(filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            buffer.flush()
            os.fsync(buffer.fileno())
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        return {"error": "Failed to save video. Please try again."}

    # 3. Verify file is valid
    file_size = os.path.getsize(filename)
    logger.info(f"User {user.id} uploaded {filename} ({file_size} bytes) for sport={sport}")

    if file_size < 1000:
        return {"error": "Video file is too small or corrupted. Please try uploading again."}

    # 4. Always convert and compress video for compatibility and memory
    try:
        from analysis.pose_detection import convert_video
        converted_filename = convert_video(filename)
        logger.info(f"Using converted video: {converted_filename}")
    except Exception as e:
        logger.warning(f"Video conversion failed: {e}")
        converted_filename = filename

    # 5. Get previous score for improvement tracking
    try:
        last_log = (
            db.query(PerformanceLog)
            .filter(
                PerformanceLog.user_id == user.id,
                PerformanceLog.sport == sport,
            )
            .order_by(PerformanceLog.created_at.desc())
            .first()
        )
        previous_score = int(last_log.score) if last_log and last_log.score else None
    except Exception as e:
        logger.warning(f"Could not get previous score: {e}")
        previous_score = None

    # 6. Run pose analysis
    try:
        from analysis.process_video import analyze_video as run_analysis
        result = run_analysis(
            converted_filename,
            sport=sport,
            previous_score=previous_score,
        )
    except Exception as e:
        logger.error(f"Analysis crashed: {e}", exc_info=True)
        return {"error": f"Analysis failed: {str(e)}"}

    if "error" in result:
        return result

    # 7. Enrich with GPT feedback for Pro/Elite users
    if has_feature(user, "detailed_feedback"):
        try:
            gpt = generate_gpt_feedback(
                metrics=result,
                sport=sport,
                personality=user.personality_mode or "supportive",
            )
            result["gpt_feedback"] = gpt
        except Exception as e:
            logger.warning(f"GPT feedback failed: {e}")

    # 8. Save performance log
    try:
        log = PerformanceLog(
            user_id=user.id,
            sport=sport,
            score=result.get("score"),
            reps=result.get("reps_completed"),
            video_path=converted_filename,
            metrics={
                "form_issues": result.get("form_issues", []),
                "coaching_tips": result.get("coaching_tips", []),
            },
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save performance log: {e}")

    # 9. Push notification
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