import os
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.performance_log import PerformanceLog

logger = logging.getLogger(__name__)


def generate_weekly_report(user, db: Session) -> dict:
    one_week_ago = datetime.utcnow() - timedelta(days=7)

    logs = (
        db.query(PerformanceLog)
        .filter(
            PerformanceLog.user_id == user.id,
            PerformanceLog.created_at >= one_week_ago,
        )
        .order_by(PerformanceLog.created_at.asc())
        .all()
    )

    if not logs:
        return {"message": "No sessions this week. Upload videos to generate your report."}

    scores = [log.score for log in logs if log.score is not None]
    avg = round(sum(scores) / len(scores), 2) if scores else 0

    ai_report = _call_gpt_weekly(
        username=user.username,
        scores=scores,
        session_count=len(logs),
        personality=getattr(user, "personality_mode", "supportive"),
    )

    return {
        "sessions_this_week": len(logs),
        "starting_score": scores[0] if scores else None,
        "latest_score": scores[-1] if scores else None,
        "average_score": avg,
        "ai_coaching_report": ai_report,
    }


def _call_gpt_weekly(username: str, scores: list, session_count: int, personality: str) -> str:
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "sk-xxxxx":
        logger.warning("OPENAI_API_KEY not set — skipping GPT report.")
        return "AI report unavailable — OpenAI API key not configured."

    client = OpenAI(api_key=api_key)

    PERSONALITY_TONES = {
        "supportive": "Encouraging, motivating, positive and confidence-building.",
        "hardcore": "Direct, intense, disciplined, high-performance focused.",
        "technical": "Analytical, data-driven, precise and objective.",
    }
    tone = PERSONALITY_TONES.get(personality, PERSONALITY_TONES["supportive"])

    prompt = f"""
You are an elite athletic performance coach.
Coaching style: {tone}

Athlete: {username}
Sessions this week: {session_count}
Performance scores: {scores}

Write a structured weekly coaching report including:
1. Performance trend analysis
2. Biggest improvement observation
3. Areas that need work
4. Specific training focus for next week
5. Motivational closing paragraph

Keep it under 400 words. Be specific and actionable.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional performance coach."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.warning(f"GPT weekly report failed: {e}")
        return "Unable to generate AI report at this time. Please try again later."