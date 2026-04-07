import logging
import httpx

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def send_push_notification(
    token: str,
    title: str,
    body: str,
    data: dict = None,
):
    """Send a push notification via Expo Push Service."""
    if not token or not token.startswith("ExponentPushToken"):
        logger.warning(f"Invalid push token: {token}")
        return False

    payload = {
        "to": token,
        "title": title,
        "body": body,
        "sound": "default",
        "priority": "high",
        "data": data or {},
    }

    try:
        with httpx.Client(timeout=10) as client:
            response = client.post(
                EXPO_PUSH_URL,
                json=payload,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip, deflate",
                    "Content-Type": "application/json",
                },
            )
            result = response.json()
            if result.get("data", {}).get("status") == "ok":
                logger.info(f"Push sent successfully to {token[:30]}...")
                return True
            else:
                logger.warning(f"Push send failed: {result}")
                return False
    except Exception as e:
        logger.error(f"Push notification error: {e}")
        return False


def send_analysis_complete_notification(token: str, sport: str, score: int):
    """Notify user their analysis is ready."""
    sport_emoji = {
        "basketball": "🏀", "soccer": "⚽", "tennis": "🎾",
        "golf": "⛳", "baseball": "⚾", "volleyball": "🏐",
        "swimming": "🏊", "waterpolo": "🤽", "pickleball": "🏓",
        "badminton": "🏸", "boxing": "🥊",
    }.get(sport, "🏅")

    score_label = (
        "Elite performance! 🔥" if score >= 85 else
        "Great session! 💪" if score >= 70 else
        "Keep improving! 📈"
    )

    return send_push_notification(
        token=token,
        title=f"{sport_emoji} Analysis Complete!",
        body=f"Your {sport.title()} score: {score}/100 — {score_label}",
        data={"type": "analysis_complete", "sport": sport, "score": score},
    )


def send_training_reminder_notification(token: str, sport: str):
    """Send daily training reminder."""
    sport_emoji = {
        "basketball": "🏀", "soccer": "⚽", "tennis": "🎾",
        "golf": "⛳", "baseball": "⚾", "volleyball": "🏐",
        "swimming": "🏊", "waterpolo": "🤽", "pickleball": "🏓",
        "badminton": "🏸", "boxing": "🥊",
    }.get(sport, "🏅")

    return send_push_notification(
        token=token,
        title=f"{sport_emoji} Time to train!",
        body=f"Upload a {sport.title()} video today to keep your streak going 🔥",
        data={"type": "training_reminder", "sport": sport},
    )


def send_weekly_report_notification(token: str, avg_score: float, improvement: float):
    """Send weekly progress report notification."""
    trend = "📈 Up" if improvement > 0 else "📉 Down"
    return send_push_notification(
        token=token,
        title="📊 Your Weekly Report is Ready",
        body=f"Avg score: {avg_score:.0f}/100 • {trend} {abs(improvement):.1f}% this week",
        data={"type": "weekly_report"},
    )