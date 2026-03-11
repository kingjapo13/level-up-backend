import logging
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


def _weekly_reports_job():
    from app.db.database import SessionLocal
    from app.models.user import User
    from services.elite_ai_report_service import generate_elite_report
    from services.ai_report_service import generate_weekly_report
    from services.email_service import send_email

    db = SessionLocal()
    try:
        users = db.query(User).all()
        for user in users:
            tier = user.subscription.tier if user.subscription and user.subscription.is_active else "free"
            if tier not in ("pro", "elite"):
                continue
            if not user.email:
                continue
            if tier == "elite":
                report = generate_elite_report(user, db)
                body = report.get("ai_report", "No report generated.")
            else:
                report = generate_weekly_report(user, db)
                body = report.get("ai_coaching_report", "No report generated.")
            send_email(
                to=user.email,
                subject="Your Weekly LevelUp Coaching Report 🏆",
                body=body,
            )
            logger.info(f"Weekly report sent to {user.email} (tier={tier})")
    except Exception as e:
        logger.error(f"Weekly reports job failed: {e}")
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
    return scheduler