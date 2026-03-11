import logging
import os

logger = logging.getLogger(__name__)

_firebase_initialized = False


def _init_firebase():
    global _firebase_initialized
    if _firebase_initialized:
        return
    try:
        import firebase_admin
        from firebase_admin import credentials
        key_path = os.getenv("FIREBASE_KEY_PATH", "firebase_key.json")
        if not os.path.exists(key_path):
            logger.warning(f"Firebase key not found at {key_path} — push notifications disabled.")
            return
        cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        logger.info("Firebase initialized.")
    except Exception as e:
        logger.warning(f"Firebase init failed: {e}")


def send_push_notification(token: str, title: str, body: str) -> bool:
    _init_firebase()
    if not _firebase_initialized:
        logger.warning("Push notification skipped — Firebase not initialized.")
        return False
    try:
        from firebase_admin import messaging
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            token=token,
        )
        response = messaging.send(message)
        logger.info(f"Push sent: {response}")
        return True
    except Exception as e:
        logger.warning(f"Push notification failed: {e}")
        return False