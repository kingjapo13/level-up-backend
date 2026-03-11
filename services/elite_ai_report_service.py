import os
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.performance_log import PerformanceLog

logger = logging.getLogger(__name__)

PERSONALITY_TONES = {
    "supportive": "Encouraging, motivating, positive and confidence-building.",
    "hardcore": "Direct, intense, disciplined, high-performance focused.",
    "technical": "Analytical, data-driven, precise and objective.",
}


def generate_elite_report(user, db: Session) -> dict:
    now = datetime.utcnow()
    start_this_week = now - timedelta(days=7)
    start_last_week = now - timedelta(days=14)

    this_week_logs = (
        db.query(PerformanceLog)
        .filter(
            PerformanceLog.user_id == user.id,
            PerformanceLog.created_at >= start_this_week,
        )
        .all()
    )

    last_week_logs = (
        db.query(PerformanceLog)
        .filter(
            PerformanceLog.user_id == user.id,
            PerformanceLog.created_at >= start_last_week,
            PerformanceLog.created_at < start_this_week,
        )
        .all()
    )

    if not this_week_logs:
        return {"message": "No sessions logged this week."}

    sport = this_week_logs[0].sport
    report_text = _call_gpt_elite(
        user=user,
        sport=sport,
        this_week=this_week_logs,
        last_week=last_week_logs,
    )

    scores = [l.score for l in this_week_logs if l.score is not None]
    avg = round(sum(scores) / len(scores), 1) if scores else 0

    return {
        "sport": sport,
        "sessions_this_week": len(this_week_logs),
        "average_score": avg,
        "ai_report": report_text,
    }


def _call_gpt_elite(user, sport: str, this_week: list, last_week: list) -> str:
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "sk-xxxxx":
        logger.warning("OPENAI_API_KEY not set — skipping elite GPT report.")
        return "AI report unavailable — OpenAI API key not configured."

    client = OpenAI(api_key=api_key)

    personality = PERSONALITY_TONES.get(
        getattr(user, "personality_mode", "supportive"),
        PERSONALITY_TONES["supportive"],
    )

    def extract(logs):
        return [{"score": l.score, "reps": l.reps, "sport": l.sport} for l in logs]

    prompt = f"""
You are an elite {sport} performance coach.
Coaching style: {personality}

THIS WEEK DATA:
{extract(this_week)}

LAST WEEK DATA:
{extract(last_week) or "No data from last week."}

Write a structured weekly coaching report including:
1. Overall trend vs last week
2. Detailed performance analysis
3. Biggest improvement
4. Biggest weakness
5. Specific training prescription for next week
6. Motivational closing paragraph

Limit to 500 words.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a world-class athletic performance coach."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.warning(f"Elite GPT report failed: {e}")
        return "Unable to generate AI report at this time."