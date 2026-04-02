import os
import logging
import json

logger = logging.getLogger(__name__)


def generate_gpt_feedback(metrics: dict, sport: str, personality: str = "supportive") -> str:
    """Generates detailed personalized GPT coaching feedback."""
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    personality_prompts = {
        "supportive": "Be encouraging and positive. Celebrate what they did well before addressing issues.",
        "hardcore": "Be direct and intense. No sugarcoating — focus purely on what needs to improve.",
        "technical": "Be data-driven and precise. Focus on biomechanics, angles, and specific metrics.",
    }

    personality_style = personality_prompts.get(
        personality, personality_prompts["supportive"]
    )

    form_issues = metrics.get("form_issues", [])
    coaching_tips = metrics.get("coaching_tips", [])
    score = metrics.get("score", 0)
    reps = metrics.get("reps_completed", 0)

    issues_text = (
        "\n".join(f"- {i}" for i in form_issues)
        if form_issues else "No major form issues detected"
    )
    tips_text = (
        "\n".join(
            f"- {t if isinstance(t, str) else t.get('tip', '')}"
            for t in coaching_tips
        )
        if coaching_tips else "None"
    )

    prompt = f"""You are an expert {sport} coach analyzing an athlete's training video.

Here is their performance data:
- Sport: {sport}
- Performance Score: {score}/100
- Reps completed: {reps}
- Form issues detected by AI:
{issues_text}
- Coaching tips generated:
{tips_text}

Coaching style: {personality_style}

Write detailed coaching feedback with exactly these 3 sections:

**What You Did Well:**
Write 2-3 specific sentences about what they did correctly based on their score and any lack of issues. Be specific to {sport}.

**What Needs Improvement:**
Write 2-3 specific sentences directly addressing each form issue detected. Give concrete actionable advice for each one. If no issues were detected mention areas to take to the next level.

**Your Action Plan:**
Write 2-3 specific sentences with exactly what they should focus on in their next training session to improve their score. Be very specific to {sport} technique.

Keep the total response under 250 words. Be specific not generic. Reference their actual score and actual form issues."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"GPT feedback API call failed: {e}")
        return _fallback_feedback(sport, score, form_issues)


def generate_training_plan(metrics: dict, sport: str) -> dict:
    """Generates a 3-day AI training plan based on performance."""
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    form_issues = metrics.get("form_issues", [])
    score = metrics.get("score", 0)
    issues_text = (
        "\n".join(f"- {i}" for i in form_issues)
        if form_issues else "General improvement"
    )

    prompt = f"""You are an expert {sport} coach. Create a 3-day training plan to improve this athlete.

Current performance:
- Sport: {sport}
- Score: {score}/100
- Issues to address:
{issues_text}

Respond ONLY with valid JSON in exactly this format with no extra text:
{{
  "plan_title": "3-Day {sport.title()} Improvement Plan",
  "focus": "Main focus area based on issues",
  "days": [
    {{
      "day": 1,
      "title": "Day 1 - Title",
      "focus": "Focus area",
      "duration_minutes": 30,
      "drills": [
        {{
          "name": "Drill name",
          "sets": 3,
          "reps": "10 reps",
          "instruction": "How to perform it",
          "targets": "What it improves"
        }}
      ]
    }}
  ]
}}

Generate exactly 3 days with exactly 3-4 drills each. Focus on fixing the detected issues."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.7,
        )
        text = response.choices[0].message.content.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        logger.warning(f"Training plan generation failed: {e}")
        return _fallback_training_plan(sport)


def generate_technique_guide(sport: str, form_issues: list, personality: str = "supportive") -> dict:
    """Generates a technique guide with correct form steps."""
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    issues_text = (
        "\n".join(form_issues)
        if form_issues else "No major issues detected"
    )

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

Generate exactly 4-5 steps focused on fixing the detected issues. Generate exactly 3 image search terms."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.7,
        )
        text = response.choices[0].message.content.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        logger.warning(f"Technique guide generation failed: {e}")
        return _fallback_technique_guide(sport, form_issues)


def _fallback_feedback(sport: str, score: float, form_issues: list) -> str:
    """Fallback feedback if GPT fails."""
    issues_text = ""
    if form_issues:
        issues_text = " Issues detected: " + ". ".join(form_issues) + "."

    if score >= 80:
        return (
            f"**What You Did Well:**\n"
            f"Strong {sport} performance with a score of {score}/100. "
            f"Your overall movement pattern shows solid fundamentals and good athleticism.\n\n"
            f"**What Needs Improvement:**\n"
            f"{issues_text if issues_text else 'No major form issues detected — focus on consistency and refinement.'}\n\n"
            f"**Your Action Plan:**\n"
            f"Upload another video next session to track your progress. "
            f"Focus on maintaining your strong technique while working on the areas identified above."
        )
    elif score >= 60:
        return (
            f"**What You Did Well:**\n"
            f"Decent {sport} effort with a score of {score}/100. "
            f"You are showing the right intent and basic movement patterns.\n\n"
            f"**What Needs Improvement:**\n"
            f"{issues_text if issues_text else 'Work on improving your range of motion and consistency across reps.'}\n\n"
            f"**Your Action Plan:**\n"
            f"Focus on slow deliberate practice before adding speed. "
            f"Film yourself from the side to check your form alignment."
        )
    else:
        return (
            f"**What You Did Well:**\n"
            f"You got out there and put in the work — that is the first step. "
            f"Score: {score}/100.\n\n"
            f"**What Needs Improvement:**\n"
            f"{issues_text if issues_text else 'Focus on the fundamental movement patterns for your sport.'}\n\n"
            f"**Your Action Plan:**\n"
            f"Start with the basics. Practice at slow speed first to build muscle memory. "
            f"Use the training plan to build up gradually."
        )


def _fallback_training_plan(sport: str) -> dict:
    """Fallback training plan if GPT fails."""
    return {
        "plan_title": f"3-Day {sport.title()} Improvement Plan",
        "focus": "Form and technique fundamentals",
        "days": [
            {
                "day": 1,
                "title": "Day 1 - Foundation",
                "focus": "Basic technique",
                "duration_minutes": 30,
                "drills": [
                    {
                        "name": "Warm Up",
                        "sets": 1,
                        "reps": "5 minutes",
                        "instruction": "Light cardio and dynamic stretching",
                        "targets": "Injury prevention"
                    },
                    {
                        "name": "Form Practice",
                        "sets": 3,
                        "reps": "10 reps",
                        "instruction": f"Slow controlled {sport} movement focusing on technique",
                        "targets": "Muscle memory"
                    },
                    {
                        "name": "Cool Down",
                        "sets": 1,
                        "reps": "5 minutes",
                        "instruction": "Static stretching",
                        "targets": "Recovery"
                    },
                ]
            },
            {
                "day": 2,
                "title": "Day 2 - Strength",
                "focus": "Building power",
                "duration_minutes": 35,
                "drills": [
                    {
                        "name": "Core Stability",
                        "sets": 3,
                        "reps": "30 seconds",
                        "instruction": "Plank hold with focus on breathing",
                        "targets": "Core strength"
                    },
                    {
                        "name": "Sport Specific Drill",
                        "sets": 4,
                        "reps": "8 reps",
                        "instruction": f"Focused {sport} technique drill at 75% intensity",
                        "targets": "Power and control"
                    },
                    {
                        "name": "Balance Work",
                        "sets": 2,
                        "reps": "45 seconds each side",
                        "instruction": "Single leg balance with eyes closed",
                        "targets": "Stability"
                    },
                ]
            },
            {
                "day": 3,
                "title": "Day 3 - Game Speed",
                "focus": "Speed and reaction",
                "duration_minutes": 40,
                "drills": [
                    {
                        "name": "Speed Drill",
                        "sets": 5,
                        "reps": "6 reps",
                        "instruction": f"Full speed {sport} movement with proper form",
                        "targets": "Explosiveness"
                    },
                    {
                        "name": "Reaction Training",
                        "sets": 3,
                        "reps": "10 reps",
                        "instruction": "Partner or solo reaction drill",
                        "targets": "Reaction time"
                    },
                    {
                        "name": "Full Practice",
                        "sets": 1,
                        "reps": "10 minutes",
                        "instruction": f"Apply everything in a full {sport} practice session",
                        "targets": "Integration"
                    },
                ]
            },
        ]
    }


def _fallback_technique_guide(sport: str, form_issues: list) -> dict:
    """Fallback technique guide if GPT fails."""
    guides = {
        "squat": {
            "title": "Perfect Squat Form Guide",
            "intro": "A proper squat builds strength safely and effectively.",
            "steps": [
                {"number": 1, "title": "Foot Position", "description": "Stand with feet shoulder-width apart, toes pointed slightly outward at 15-30 degrees.", "cue": "Shoulder width"},
                {"number": 2, "title": "Brace Your Core", "description": "Take a deep breath and brace your core as if about to take a punch.", "cue": "Big breath, brace"},
                {"number": 3, "title": "Initiate the Descent", "description": "Push hips back first, then bend your knees. Keep chest up and back straight.", "cue": "Hips back first"},
                {"number": 4, "title": "Hit Depth", "description": "Squat until thighs are parallel to the floor or below. Keep knees tracking over toes.", "cue": "Thighs parallel"},
                {"number": 5, "title": "Drive Up", "description": "Push through your heels to stand back up. Keep chest tall throughout.", "cue": "Push through heels"},
            ],
            "key_mistakes": [
                {"mistake": "Knee Cave", "fix": "Push knees outward — spread the floor apart with your feet"},
                {"mistake": "Forward Lean", "fix": "Keep chest up and look slightly above horizontal"},
                {"mistake": "Heel Rise", "fix": "Push weight through your heels not your toes"},
            ],
            "image_searches": [
                "proper squat form side view",
                "squat depth parallel correct technique",
                "squat knee alignment correct form"
            ],
            "pro_tip": "Record yourself from the side every few sessions to check depth and back angle.",
        },
        "basketball": {
            "title": "Perfect Basketball Shooting Form",
            "intro": "Consistent shooting form is the foundation of a reliable shot.",
            "steps": [
                {"number": 1, "title": "Athletic Stance", "description": "Feet shoulder-width apart, knees slightly bent, weight on balls of feet.", "cue": "Athletic stance"},
                {"number": 2, "title": "Hand Position", "description": "Shooting hand under the ball, guide hand on the side. Ball on fingertips not palm.", "cue": "Fingertips not palm"},
                {"number": 3, "title": "Elbow Alignment", "description": "Shooting elbow directly under the ball forming an L-shape pointing at the basket.", "cue": "Elbow under ball"},
                {"number": 4, "title": "Rise and Extend", "description": "Rise through your legs first then extend your shooting arm in one fluid motion.", "cue": "Legs then arms"},
                {"number": 5, "title": "Follow Through", "description": "Snap your wrist forward, fingers pointing down at the basket. Hold the follow through.", "cue": "Goose neck follow through"},
            ],
            "key_mistakes": [
                {"mistake": "Side Spin", "fix": "Keep your guide hand still — it should not push the ball"},
                {"mistake": "Flat Shot", "fix": "Aim for the back of the rim and increase your arc"},
                {"mistake": "Rushing", "fix": "One fluid motion from legs to fingertips"},
            ],
            "image_searches": [
                "basketball shooting form correct technique",
                "NBA shooting form elbow alignment",
                "basketball follow through wrist snap"
            ],
            "pro_tip": "Practice form shooting from 3 feet away until the motion is completely automatic.",
        },
    }

    default = {
        "title": f"Perfect {sport.title()} Form Guide",
        "intro": f"Mastering correct {sport} technique improves performance and prevents injury.",
        "steps": [
            {"number": 1, "title": "Starting Position", "description": f"Set up your body correctly before beginning the {sport} movement.", "cue": "Athletic stance"},
            {"number": 2, "title": "Core Engagement", "description": "Keep your core braced throughout the entire movement for stability.", "cue": "Brace your core"},
            {"number": 3, "title": "Movement Execution", "description": f"Execute the {sport} movement with controlled deliberate motion.", "cue": "Slow and controlled"},
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