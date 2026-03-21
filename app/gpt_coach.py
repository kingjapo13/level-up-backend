import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

PERSONALITY_PROMPTS = {
    "supportive": (
        "You are an encouraging, world-class sports coach. "
        "Be positive, specific, and motivating. "
        "Celebrate what they did well before addressing issues. "
        "Use an upbeat, energetic tone."
    ),
    "hardcore": (
        "You are a demanding, no-nonsense elite sports coach. "
        "Be direct, intense, and push the athlete hard. "
        "Don't sugarcoat feedback. Focus on what needs to improve immediately."
    ),
    "technical": (
        "You are a biomechanics expert and sports scientist. "
        "Give precise, data-driven coaching based on angles, timing and metrics. "
        "Use technical terminology and be highly specific."
    ),
}


def generate_gpt_feedback(
    metrics: dict,
    sport: str = "general",
    personality: str = "supportive",
) -> Optional[str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key in ("sk-xxxxx", "sk_test"):
        logger.warning("OPENAI_API_KEY not configured")
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        system_prompt = PERSONALITY_PROMPTS.get(
            personality, PERSONALITY_PROMPTS["supportive"]
        )

        score = metrics.get("score", 0)
        reps = metrics.get("reps_completed", 0)
        form_issues = metrics.get("form_issues", [])
        tips = metrics.get("coaching_tips", [])
        summary = metrics.get("summary", "")
        improvement = metrics.get("improvement", "")

        user_prompt = f"""Athlete Performance Analysis — {sport.upper()}

Score: {score}/100
Reps Completed: {reps}
Summary: {summary}
{f"Progress: {improvement}" if improvement else ""}

Form Issues Detected:
{chr(10).join(f"- {issue}" for issue in form_issues) if form_issues else "- No major form issues detected"}

Current Coaching Tips:
{chr(10).join(f"- {tip.get('tip', tip) if isinstance(tip, dict) else tip}" for tip in tips) if tips else "- N/A"}

Based on this analysis, provide personalized coaching feedback:
1. Start with what they did well (1-2 sentences)
2. Give 2-3 specific actionable improvements
3. Give one drill or exercise to fix the biggest issue
4. End with a motivational sentence

Keep it under 200 words. Be specific to {sport}. Sound like a real coach talking to an athlete."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=300,
            temperature=0.7,
        )
        return response.choices[0].message.content

    except Exception as e:
        logger.warning(f"GPT feedback failed: {e}")
        return None