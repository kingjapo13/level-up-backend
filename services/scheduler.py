import logging
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


def _weekly_reports_job():
    """Sends weekly AI reports to Pro/Elite users every Sunday at 8am."""
    try:
        from app.db.database import SessionLocal
        from app.models.user import User
        from services.ai_report_service import generate_weekly_report

        db = SessionLocal()
        try:
            users = db.query(User).all()
            for user in users:
                if not user.subscription:
                    continue
                tier = user.subscription.effective_tier
                if tier not in ("pro", "elite"):
                    continue
                try:
                    generate_weekly_report(user, db)
                    logger.info(f"Weekly report sent to {user.username}")
                except Exception as e:
                    logger.warning(f"Weekly report failed for {user.username}: {e}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Weekly reports job failed: {e}")


def _training_reminders_job():
    """Sends training reminders every Monday at 7am."""
    try:
        from app.db.database import SessionLocal
        from app.models.user import User
        from services.push_service import send_push_notification

        db = SessionLocal()
        try:
            users = db.query(User).all()
            for user in users:
                if not user.device_token:
                    continue
                try:
                    send_push_notification(
                        token=user.device_token,
                        title="Time to train! 💪",
                        body="Upload a video to track your progress this week.",
                    )
                except Exception as e:
                    logger.warning(f"Reminder failed for {user.username}: {e}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Training reminders job failed: {e}")


def _trial_expiry_job():
    """Sends trial expiry warning emails daily at 9am."""
    try:
        from app.db.database import SessionLocal
        from app.models.user import User
        from datetime import datetime, timedelta
        from services.email_service import send_trial_expiry_warning, send_trial_expired

        db = SessionLocal()
        try:
            users = db.query(User).all()
            now = datetime.utcnow()

            for user in users:
                if not user.subscription or not user.subscription.is_trial:
                    continue
                if not user.email:
                    continue

                trial_end = user.subscription.trial_end
                if not trial_end:
                    continue

                days_left = (trial_end - now).days

                if days_left == 2:
                    try:
                        send_trial_expiry_warning(
                            to=user.email,
                            username=user.username,
                            days_left=2,
                        )
                        logger.info(f"Trial warning sent to {user.email}")
                    except Exception as e:
                        logger.warning(f"Trial warning failed for {user.email}: {e}")

                elif days_left == -1:
                    try:
                        send_trial_expired(
                            to=user.email,
                            username=user.username,
                        )
                        logger.info(f"Trial expired email sent to {user.email}")
                    except Exception as e:
                        logger.warning(f"Trial expired email failed for {user.email}: {e}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Trial expiry job failed: {e}")


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()

    # Weekly reports — every Sunday at 8am
    scheduler.add_job(
        _weekly_reports_job,
        "cron",
        day_of_week="sun",
        hour=8,
    )

    # Training reminders — every Monday at 7am
    scheduler.add_job(
        _training_reminders_job,
        "cron",
        day_of_week="mon",
        hour=7,
    )

    # Trial expiry emails — daily at 9am
    scheduler.add_job(
        _trial_expiry_job,
        "cron",
        hour=9,
    )

    scheduler.start()
    logger.info("Scheduler started.")
    return scheduler