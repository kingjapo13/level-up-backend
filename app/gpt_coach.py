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
        import httpx
        from openai import OpenAI
        http_client = httpx.Client()
        client = OpenAI(api_key=api_key, http_client=http_client)

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
        def generate_technique_guide(sport: str, form_issues: list, personality: str = "supportive") -> dict:
    """
    Generates a technique guide with correct form steps and reference image search terms.
    """
    import os
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    issues_text = "\n".join(form_issues) if form_issues else "No major issues detected"

    prompt = f"""You are an expert {sport} coach. Generate a technique guide for correct {sport} form.

Form issues detected in this athlete's video:
{issues_text}

Respond ONLY with valid JSON in exactly this format with no extra text:
{{
  "title": "Perfect {sport.title()} Form Guide",
  "intro": "One sentence intro about correct {sport} form",
  "steps": [
    {{
      "number": 1,
      "title": "Step title",
      "description": "Detailed description of this form checkpoint",
      "cue": "Short coaching cue like 'chest up' or 'knees out'"
    }}
  ],
  "key_mistakes": [
    {{
      "mistake": "Common mistake name",
      "fix": "How to fix it"
    }}
  ],
  "image_searches": [
    "specific search term for correct {sport} form image 1",
    "specific search term for correct {sport} form image 2",
    "specific search term for correct {sport} form image 3"
  ],
  "pro_tip": "One advanced tip from a professional coach perspective"
}}

Generate exactly 4-5 steps focused on fixing the detected issues. Generate exactly 3 image search terms that would find clear reference images of correct {sport} form."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.7,
        )
        import json
        text = response.choices[0].message.content.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Technique guide failed: {e}")
        return _fallback_technique_guide(sport, form_issues)


def _fallback_technique_guide(sport: str, form_issues: list) -> dict:
    """Fallback guide if GPT fails."""
    guides = {
        "squat": {
            "title": "Perfect Squat Form Guide",
            "intro": "A proper squat builds strength safely and effectively.",
            "steps": [
                {"number": 1, "title": "Foot Position", "description": "Stand with feet shoulder-width apart, toes pointed slightly outward at 15-30 degrees.", "cue": "Shoulder width"},
                {"number": 2, "title": "Brace Your Core", "description": "Take a deep breath and brace your core as if you are about to take a punch.", "cue": "Big breath, brace"},
                {"number": 3, "title": "Initiate the Descent", "description": "Push your hips back first, then bend your knees. Keep your chest up and back straight.", "cue": "Hips back first"},
                {"number": 4, "title": "Hit Depth", "description": "Squat until your thighs are parallel to the floor or below. Keep knees tracking over toes.", "cue": "Thighs parallel"},
                {"number": 5, "title": "Drive Up", "description": "Push through your heels to stand back up. Keep chest tall throughout the movement.", "cue": "Push through heels"},
            ],
            "key_mistakes": [
                {"mistake": "Knee Cave", "fix": "Push knees outward — think about spreading the floor apart with your feet"},
                {"mistake": "Forward Lean", "fix": "Keep chest up and look slightly above horizontal"},
                {"mistake": "Heel Rise", "fix": "Push weight through your heels, not your toes"},
            ],
            "image_searches": [
                "proper squat form side view",
                "squat depth parallel correct technique",
                "squat knee alignment correct form"
            ],
            "pro_tip": "Record yourself from the side to check your depth and back angle every few sessions.",
        },
        "basketball": {
            "title": "Perfect Basketball Shooting Form",
            "intro": "Consistent shooting form is the foundation of a reliable shot.",
            "steps": [
                {"number": 1, "title": "Triple Threat Stance", "description": "Feet shoulder-width apart, knees slightly bent, ball in triple threat position.", "cue": "Athletic stance"},
                {"number": 2, "title": "Hand Position", "description": "Shooting hand under the ball, guide hand on the side. Fingers spread, ball on fingertips.", "cue": "Fingertips, not palm"},
                {"number": 3, "title": "Elbow Alignment", "description": "Shooting elbow directly under the ball, forming an L-shape. Elbow points at the basket.", "cue": "Elbow under ball"},
                {"number": 4, "title": "Upward Motion", "description": "Rise up through your legs first, then extend your shooting arm in one fluid motion.", "cue": "Legs then arms"},
                {"number": 5, "title": "Follow Through", "description": "Snap your wrist forward, fingers pointing down at the basket. Hold the follow through.", "cue": "Goose neck follow through"},
            ],
            "key_mistakes": [
                {"mistake": "Side Spin", "fix": "Keep your guide hand still — it should not push the ball"},
                {"mistake": "Flat Shot", "fix": "Aim for the back of the rim and increase your arc"},
                {"mistake": "Rushing", "fix": "Slow down and focus on one fluid motion from legs to fingertips"},
            ],
            "image_searches": [
                "basketball shooting form correct technique",
                "NBA shooting form elbow alignment",
                "basketball follow through wrist snap"
            ],
            "pro_tip": "Practice form shooting from 3 feet away from the basket until the motion is automatic.",
        },
    }

    default = {
        "title": f"Perfect {sport.title()} Form Guide",
        "intro": f"Mastering correct {sport} technique will improve your performance and prevent injury.",
        "steps": [
            {"number": 1, "title": "Starting Position", "description": f"Set up your body correctly before beginning the {sport} movement.", "cue": "Athletic stance"},
            {"number": 2, "title": "Core Engagement", "description": "Keep your core braced throughout the entire movement for stability.", "cue": "Brace your core"},
            {"number": 3, "title": "Movement Execution", "description": f"Execute the {sport} movement with controlled, deliberate motion.", "cue": "Slow and controlled"},
            {"number": 4, "title": "Follow Through", "description": "Complete the full range of motion on every rep for maximum benefit.", "cue": "Full range of motion"},
        ],
        "key_mistakes": [
            {"mistake": "Poor Posture", "fix": "Keep chest up and back straight throughout"},
            {"mistake": "Rushing", "fix": "Slow down and focus on technique over speed"},
        ],
        "image_searches": [
            f"correct {sport} form technique",
            f"proper {sport} body position",
            f"{sport} coaching form guide"
        ],
        "pro_tip": f"Film yourself from the side every few sessions to track your {sport} form improvements.",
    }

    return guides.get(sport.lower(), default)