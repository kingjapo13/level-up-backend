import logging
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


def _trial_expiry_job():
    """Sends trial expiry warning emails on day 5 and expired emails on day 8."""
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

            # Send warning on day 5 (2 days before expiry)
            if days_left == 2:
                send_trial_expiry_warning(
                    to=user.email,
                    username=user.username,
                    days_left=2,
                )
                logger.info(f"Trial warning sent to {user.email}")

            # Send expired email day after expiry
            elif days_left == -1:
                send_trial_expired(
                    to=user.email,
                    username=user.username,
                )
                logger.info(f"Trial expired email sent to {user.email}")

    except Exception as e:
        logger.error(f"Trial expiry job failed: {e}")
    finally:
        db.close()


def _training_reminders_job():
    from app.db.database import SessionLocal
    from app.models.user import User
    from services.training_reminders import send_training_reminder

    db = SessionLocal()
    try:
        users = db.query(User).filter(User.device_token.isnot(None)).all()
        for user in users:
            send_training_reminder(user)
    except Exception as e:
        logger.error(f"Training reminders job failed: {e}")
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(_weekly_reports_job, "cron", day_of_week="sun", hour=8)
    scheduler.add_job(_training_reminders_job, "cron", day_of_week="mon", hour=7)
    scheduler.start()
    logger.info("Scheduler started.")
    # Trial expiry emails — check daily at 9am
    scheduler.add_job(_trial_expiry_job, "cron", hour=9)
    return scheduler