import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

PERSONALITY_PROMPTS = {
    "supportive": "You are an encouraging, positive sports coach. Celebrate wins and gently correct mistakes.",
    "hardcore": "You are a demanding, no-excuses coach. Push the athlete hard and don't sugarcoat feedback.",
    "technical": "You are a technical biomechanics expert. Give precise, data-driven coaching based on angles and metrics.",
}


def generate_gpt_feedback(
    metrics: dict,
    sport: str = "general",
    personality: str = "supportive",
) -> Optional[str]:
    # Import and create client here so it only runs when actually called
    # This way missing API key won't crash the app on startup
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "sk-xxxxx":
        logger.warning("OPENAI_API_KEY not set — skipping GPT feedback.")
        return None

    client = OpenAI(api_key=api_key)
    system_prompt = PERSONALITY_PROMPTS.get(personality, PERSONALITY_PROMPTS["supportive"])

    user_prompt = f"""
Sport: {sport}

Performance Metrics:
- Score: {metrics.get('score', 'N/A')} / 100
- Reps Completed: {metrics.get('reps_completed', 'N/A')}
- Form Issues: {', '.join(metrics.get('form_issues', [])) or 'None detected'}
- Summary: {metrics.get('summary', '')}

Based on these results, provide 3-5 specific coaching tips to help this athlete improve.
Be concise, actionable, and sport-specific.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=400,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.warning(f"GPT feedback failed: {e}")
        return None