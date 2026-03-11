import logging
from services.push_service import send_push_notification

logger = logging.getLogger(__name__)


def send_training_reminder(user):
    if not user.device_token:
        return
    send_push_notification(
        token=user.device_token,
        title="Time to Train 💪",
        body="Today's workout is ready in your LevelUp plan. Let's go!",
    )
    logger.info(f"Training reminder sent to user {user.id}")