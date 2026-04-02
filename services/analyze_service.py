import os
import uuid
import shutil
import logging

from sqlalchemy.orm import Session

from app.models.performance_log import PerformanceLog
from app.models.user import User

logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def has_feature(user: User, feature: str) -> bool:
    """Check if user's subscription tier has a feature."""
    if not user.subscription:
        return False
    tier = user.subscription.effective_tier
    features = {
        "trial":   {"gpt_feedback": True,  "training_plan": True,  "athlete_matching": False},
        "pro":     {"gpt_feedback": True,  "training_plan": False, "athlete_matching": False},
        "elite":   {"gpt_feedback": True,  "training_plan": True,  "athlete_matching": True},
        "expired": {"gpt_feedback": False, "training_plan": False, "athlete_matching": False},
        "free":    {"gpt_feedback": False, "training_plan": False, "athlete_matching": False},
    }
    return features.get(tier, {}).get(feature, False)


def enforce_upload_limit(user: User, db: Session):
    """Raises an exception if user has exceeded their upload limit."""
    from fastapi import HTTPException
    from datetime import datetime, timedelta

    if not user.subscription:
        raise HTTPException(status_code=403, detail="No active subscription found.")

    tier = user.subscription.effective_tier

    if tier == "expired":
        raise HTTPException(
            status_code=403,
            detail="Your free trial has expired. Please upgrade to continue."
        )

    limits = {
        "trial": 10,
        "pro": 1,
        "elite": 100,
        "free": 0,
    }

    limit = limits.get(tier, 0)
    if limit == 0:
        raise HTTPException(
            status_code=403,
            detail="Please upgrade to Pro or Elite to upload videos."
        )

    # Count uploads this month
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    count = db.query(PerformanceLog).filter(
        PerformanceLog.user_id == user.id,
        PerformanceLog.created_at >= month_start,
    ).count()

    if count >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"You have reached your {limit} upload limit for this month. Upgrade to Elite for 100 uploads/month."
        )


async def analyze_video(file, sport: str, db: Session, user: User) -> dict:
    """Main video analysis pipeline."""

    # 1. Check upload limit
    enforce_upload_limit(user, db)

    # 2. Save uploaded file
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

    file_size = os.path.getsize(filename)
    logger.info(f"User {user.id} uploaded {filename} ({file_size} bytes) for sport={sport}")

    if file_size < 1000:
        return {"error": "Video file is too small or corrupted. Please try uploading again."}

    # 3. Convert video
    try:
        from analysis.pose_detection import convert_video
        converted_filename = convert_video(filename)
        logger.info(f"Using converted video: {converted_filename}")
    except Exception as e:
        logger.warning(f"Video conversion failed: {e}")
        converted_filename = filename

    # 4. Get previous score for comparison
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

    # 5. Run pose analysis
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

    # 6. Get coach personality
    personality = "supportive"
    try:
        from app.models.user import User as UserModel
        if hasattr(user, 'personality_mode') and user.personality_mode:
            personality = user.personality_mode
    except Exception:
        pass

    # 7. GPT feedback
    if has_feature(user, "gpt_feedback"):
        try:
            from app.gpt_coach import generate_gpt_feedback
            gpt = generate_gpt_feedback(
                metrics=result,
                sport=sport,
                personality=personality,
            )
            result["gpt_feedback"] = gpt
        except Exception as e:
            logger.warning(f"GPT feedback failed: {e}")

    # 8. Training plan
    if has_feature(user, "training_plan"):
        try:
            from app.gpt_coach import generate_training_plan
            training_plan = generate_training_plan(
                metrics=result,
                sport=sport,
            )
            result["training_plan"] = training_plan
        except Exception as e:
            logger.warning(f"Training plan failed: {e}")

    # 9. Technique guide
    if has_feature(user, "gpt_feedback"):
        try:
            from app.gpt_coach import generate_technique_guide
            technique_guide = generate_technique_guide(
                sport=sport,
                form_issues=result.get("form_issues", []),
                personality=personality,
            )
            result["technique_guide"] = technique_guide
        except Exception as e:
            logger.warning(f"Technique guide failed: {e}")

    # 10. Save performance log
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
                "summary": result.get("summary", ""),
                "gpt_feedback": result.get("gpt_feedback", ""),
                "improvement": result.get("improvement", ""),
                "training_plan": result.get("training_plan", None),
                "annotated_frames": result.get("annotated_frames", []),
                "technique_guide": result.get("technique_guide", None),
            },
        )
        db.add(log)
        db.commit()
        logger.info(f"Saved performance log for user {user.id}")
    except Exception as e:
        logger.error(f"Failed to save performance log: {e}")

    # 11. Push notification
    try:
        if hasattr(user, 'device_token') and user.device_token:
            from services.push_service import send_push_notification
            send_push_notification(
                token=user.device_token,
                title="Analysis Ready 🏆",
                body="Your LevelUp AI coaching feedback is ready to view.",
            )
    except Exception as e:
        logger.warning(f"Push notification failed: {e}")

    return result