import logging
import os
import tempfile
import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.performance_log import PerformanceLog
from app.models.user import User

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ─── Pro Athlete Benchmarks ───────────────────────────────────────────────────
PRO_ATHLETE_BENCHMARKS = {
    "basketball": """
PROFESSIONAL BENCHMARK — NBA/Collegiate Shooting Standards:
- Score 90-100: Near-perfect NBA mechanics. Elbow perfectly under ball forming L-shape,
  45-55 degree arc, full wrist snap with goose-neck follow through held 2+ seconds,
  feet shoulder-width in balanced stance, eyes on target throughout, legs drive power up.
- Score 75-89: Solid collegiate/serious player level. Most mechanics correct with 1-2 minor issues.
- Score 55-74: Recreational player with clear fixable issues. Multiple form problems visible.
- Score 35-54: Significant form problems. Poor elbow alignment, flat arc, minimal follow through.
- Score 0-34: Major technique issues throughout. Fundamentals need complete rebuild.

Key pro indicators to look for:
- Steph Curry: consistent 47-degree arc, elbow perfectly aligned, holds follow through until ball hits rim
- Kevin Durant: high release point, full extension, textbook follow through
- Most recreational players score 40-65 — be honest and realistic with scoring""",

    "tennis": """
PROFESSIONAL BENCHMARK — ATP/WTA Tour Standards:
- Score 90-100: Near-professional mechanics. Contact point 2-3 feet in front of body,
  full hip+shoulder rotation, racket low-to-high acceleration, clean over-shoulder follow through,
  split-step timing, athletic ready position between shots.
- Score 75-89: Strong club/collegiate level. Good contact point, decent rotation, follows through.
- Score 55-74: Intermediate — contact point inconsistent, partial rotation, choppy swing.
- Score 35-54: Beginner — arm-only shots, late contact, no hip rotation.
- Score 0-34: Fundamental technique issues, no form structure.

Key pro indicators:
- Federer: contact always out in front, smooth unit turn, racket acceleration through ball
- Serena: explosive hip drive, full follow through over shoulder
- Most recreational players score 35-65 — be realistic""",

    "golf": """
PROFESSIONAL BENCHMARK — PGA/LPGA Tour Standards:
- Score 90-100: Tour-level swing mechanics. Full 90-degree shoulder turn, 45-degree hip turn,
  spine angle maintained from address through impact, complete weight transfer to lead foot,
  club path on plane, balanced finish position held for 2+ seconds.
- Score 75-89: Scratch/low-handicap level. Good rotation, reasonable spine angle, solid finish.
- Score 55-74: Mid-handicap recreational. Partial rotation, some spine angle loss, incomplete finish.
- Score 35-54: High handicap. Reverse pivot, over-the-top path, early extension, poor finish.
- Score 0-34: Major swing faults throughout, needs fundamental instruction.

Key pro indicators:
- Tiger Woods: spine angle identical at address and impact, full hip rotation, balanced finish
- Rory McIlroy: explosive hip clearance, lag maintained, complete extension through ball
- Most recreational golfers score 35-65 — be honest and calibrated""",

    "soccer": """
PROFESSIONAL BENCHMARK — Premier League/Professional Standards:
- Score 90-100: Professional-level technique. Plant foot perfectly positioned beside ball,
  full leg swing from hip, ankle locked at contact, body leaning over ball for placement,
  complete follow through pointing at target, eyes down through contact.
- Score 75-89: Academy/collegiate level. Good plant foot, decent swing, reasonable follow through.
- Score 55-74: Recreational with clear improvements needed. Plant foot off, toe-kicking evident.
- Score 35-54: Significant technique issues. Wrong contact surface, no follow through.
- Score 0-34: Complete beginner mechanics throughout.

Key pro indicators:
- Ronaldo: plant foot 6 inches beside ball, full hip rotation, locked ankle at contact, complete follow through
- Messi: deceptive body feint, perfect ball control, precise contact surface
- Most recreational players score 40-65""",

    "pickleball": """
PROFESSIONAL BENCHMARK — Professional Pickleball Association Standards:
- Score 90-100: Tournament-level mechanics. Paddle up and ready before ball arrives,
  contact point out in front of body, firm stable wrist through contact zone,
  dinks consistently landing in kitchen, smooth follow through to target,
  athletic ready position reset between every shot.
- Score 75-89: 4.0+ player level. Good preparation, consistent contact, controlled placement.
- Score 55-74: 3.0-3.5 recreational — late preparation, inconsistent contact.
- Score 35-54: Beginner — reactive play, flicking wrist, poor reset position.
- Score 0-34: Complete beginner, no structured technique.

Key pro indicators:
- Ben Johns: paddle always up, contact always out front, deceptive reset game
- Anna Leigh Waters: explosive transition, consistent dink accuracy, athletic ready position
- Most recreational players score 35-65""",

    "gym": """
PROFESSIONAL BENCHMARK — Certified Strength & Conditioning Standards:
- Score 90-100: Elite technique. Full depth (thighs parallel or below for squats),
  knees tracking over toes with no cave, neutral spine maintained throughout,
  controlled 2-3 second eccentric, explosive concentric, braced core, balanced finish.
- Score 75-89: Solid intermediate. Good depth, reasonable form, minor technique gaps.
- Score 55-74: Recreational — partial depth, some knee cave or back rounding visible.
- Score 35-54: Significant technique risks. Spine rounding, knee cave, inconsistent depth.
- Score 0-34: Major form issues creating injury risk.

Key pro indicators:
- Olympic lifters: perfect bar path, full depth, explosive drive
- Most gym-goers score 45-70 — be accurate and honest about safety""",
}

ANALYSIS_PROMPT_TEMPLATE = """You are an elite AI sports performance coach analyzing a {sport} training video.

{benchmark}

Analyze the athlete's form carefully and provide your assessment in the following JSON format:

{{
  "score": <integer 0-100 based on the professional benchmarks above>,
  "performance_label": "<ELITE|EXCELLENT|GOOD|AVERAGE|NEEDS WORK|BEGINNER>",
  "summary": "<2-3 sentence honest summary of their performance>",
  "form_issues": [
    "<specific form issue 1>",
    "<specific form issue 2>"
  ],
  "coaching_tips": [
    "<specific actionable tip 1>",
    "<specific actionable tip 2>",
    "<specific actionable tip 3>"
  ],
  "strengths": [
    "<something they did well>"
  ],
  "metrics": {{
    "overall_score": <same as score>,
    "technique": <0-100>,
    "consistency": <0-100>,
    "power_or_control": <0-100>,
    "balance": <0-100>,
    "follow_through": <0-100>
  }},
  "reps_completed": <estimated number of reps/shots/swings visible, 0 if unclear>,
  "gpt_feedback": "What You Did Well\\n<2-3 sentences>\\n\\nWhat Needs Improvement\\n<2-3 sentences>\\n\\nYour Action Plan\\n<2-3 specific steps>"
}}

SCORING GUIDELINES:
- Be realistic and calibrated. Most recreational athletes score 35-70.
- Only score 80+ if the form genuinely approaches collegiate or professional level.
- Only score 90+ for near-perfect professional-level mechanics.
- If the video is unclear, low quality, or you cannot clearly see the form, score conservatively (40-55).
- Never inflate scores. Honest feedback helps athletes improve.
- Return ONLY valid JSON, no markdown, no explanation outside the JSON."""


async def analyze_video(
    video_path: str,
    sport: str,
    user: User,
    db: Session,
    personality: str = "supportive",
) -> dict:
    """Full video analysis pipeline."""
    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
    except ImportError:
        logger.error("OpenAI not installed")
        return _fallback_result(sport)

    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set")
        return _fallback_result(sport)

    try:
        # ── 1. Get previous score for personal best comparison ──────────────
        previous_log = db.query(PerformanceLog).filter(
            PerformanceLog.user_id == user.id,
            PerformanceLog.sport == sport,
        ).order_by(PerformanceLog.created_at.desc()).first()
        previous_score = previous_log.score if previous_log else None

        # ── 2. Extract frames from video ────────────────────────────────────
        frames_b64 = await _extract_frames(video_path)
        if not frames_b64:
            logger.warning("No frames extracted — using fallback")
            return _fallback_result(sport)

        # ── 3. Build prompt with pro benchmarks ─────────────────────────────
        benchmark = PRO_ATHLETE_BENCHMARKS.get(sport.lower(), "")
        benchmark_section = f"PROFESSIONAL BENCHMARKS:\n{benchmark}" if benchmark else ""
        prompt = ANALYSIS_PROMPT_TEMPLATE.format(
            sport=sport.capitalize(),
            benchmark=benchmark_section,
        )

        # ── 4. Build GPT-4o message with frames ─────────────────────────────
        content = [{"type": "text", "text": prompt}]
        for frame_b64 in frames_b64[:8]:  # Max 8 frames
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{frame_b64}",
                    "detail": "high",
                },
            })

        # ── 5. Call GPT-4o Vision ────────────────────────────────────────────
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            max_tokens=1500,
            temperature=0.3,
        )

        raw = response.choices[0].message.content.strip()
        logger.info(f"GPT raw response length: {len(raw)}")

        # ── 6. Parse JSON response ───────────────────────────────────────────
        result = _parse_gpt_response(raw, sport)

        # ── 7. Clamp score to realistic range ───────────────────────────────
        result["score"] = max(0, min(100, result.get("score", 50)))

        # ── 8. Add sport and metadata ────────────────────────────────────────
        result["sport"] = sport

        # ── 9. Generate training plan ────────────────────────────────────────
        try:
            training_plan = await _generate_training_plan(client, sport, result)
            result["training_plan"] = training_plan
        except Exception as e:
            logger.warning(f"Training plan generation failed: {e}")
            result["training_plan"] = None

        # ── 10. Save to database ─────────────────────────────────────────────
        try:
            log = PerformanceLog(
                user_id=user.id,
                sport=sport,
                score=result.get("score"),
                reps=result.get("reps_completed", 0),
                metrics=result,
                created_at=datetime.utcnow(),
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            result["session_id"] = log.id
        except Exception as e:
            logger.error(f"Failed to save performance log: {e}", exc_info=True)
            db.rollback()

        # ── 11. Award XP ─────────────────────────────────────────────────────
        try:
            from services.xp_service import award_xp

            total_sessions = db.query(func.count(PerformanceLog.id)).filter(
                PerformanceLog.user_id == user.id
            ).scalar() or 0

            is_pb = bool(previous_score and result.get("score") and result["score"] > previous_score)
            improvement = (result["score"] - previous_score) if (previous_score and result.get("score")) else 0

            # Calculate streak
            streak = 0
            streak_logs = db.query(PerformanceLog).filter(
                PerformanceLog.user_id == user.id
            ).order_by(PerformanceLog.created_at.desc()).limit(30).all()

            today = datetime.utcnow().date()
            dates = sorted(set(
                l.created_at.date() for l in streak_logs if l.created_at
            ), reverse=True)
            for i, date in enumerate(dates):
                expected = today - timedelta(days=i)
                if date == expected:
                    streak += 1
                else:
                    break

            xp_result = award_xp(
                user_id=user.id,
                db=db,
                score=result.get("score", 0),
                form_issues=result.get("form_issues", []),
                is_personal_best=is_pb,
                streak=streak,
                total_sessions=total_sessions,
                improvement=improvement,
            )

            result["xp_earned"]       = xp_result["xp_earned"]
            result["xp_breakdown"]    = xp_result["xp_breakdown"]
            result["total_xp"]        = xp_result["total_xp"]
            result["level"]           = xp_result["level"]
            result["level_name"]      = xp_result["level_name"]
            result["leveled_up"]      = xp_result["leveled_up"]
            result["new_badges"]      = xp_result["new_badges"]
            result["xp_progress_pct"] = xp_result["progress_pct"]

            logger.info(f"XP awarded: +{xp_result['xp_earned']} to user {user.id}")
        except Exception as e:
            logger.warning(f"XP award failed (non-fatal): {e}")

        return result

    except Exception as e:
        logger.error(f"analyze_video error: {e}", exc_info=True)
        return _fallback_result(sport)


async def _extract_frames(video_path: str) -> list:
    """Extract frames from video as base64 strings."""
    try:
        import cv2
        import base64

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Could not open video: {video_path}")
            return []

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        duration = total_frames / fps

        # Extract up to 8 evenly spaced frames
        num_frames = min(8, max(3, int(duration * 2)))
        frame_indices = [int(i * total_frames / num_frames) for i in range(num_frames)]

        frames_b64 = []
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                # Resize for API efficiency
                h, w = frame.shape[:2]
                if w > 1280:
                    scale = 1280 / w
                    frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                frames_b64.append(base64.b64encode(buffer).decode('utf-8'))

        cap.release()
        logger.info(f"Extracted {len(frames_b64)} frames from video")
        return frames_b64

    except Exception as e:
        logger.error(f"Frame extraction error: {e}", exc_info=True)
        return []


def _parse_gpt_response(raw: str, sport: str) -> dict:
    """Parse GPT JSON response with fallback handling."""
    try:
        # Strip markdown code blocks if present
        clean = raw.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        data = json.loads(clean)

        # Ensure required fields
        return {
            "score":             int(data.get("score", 55)),
            "performance_label": data.get("performance_label", "AVERAGE"),
            "summary":           data.get("summary", "Analysis complete."),
            "form_issues":       data.get("form_issues", []),
            "coaching_tips":     data.get("coaching_tips", []),
            "strengths":         data.get("strengths", []),
            "metrics":           data.get("metrics", {}),
            "reps_completed":    int(data.get("reps_completed", 0)),
            "gpt_feedback":      data.get("gpt_feedback", ""),
            "annotated_frames":  data.get("annotated_frames", []),
        }
    except Exception as e:
        logger.error(f"JSON parse error: {e} | Raw: {raw[:200]}")
        return _fallback_result(sport)


async def _generate_training_plan(client, sport: str, analysis: dict) -> dict:
    """Generate a personalized 3-day training plan."""
    score = analysis.get("score", 55)
    issues = analysis.get("form_issues", [])
    issues_text = "\n".join(f"- {i}" for i in issues[:3]) if issues else "- General form improvement"

    prompt = f"""Create a focused 3-day training plan for a {sport} athlete who scored {score}/100.

Their main form issues:
{issues_text}

Return ONLY valid JSON:
{{
  "plan_title": "<motivating title>",
  "focus": "<main focus area>",
  "days": [
    {{
      "day": 1,
      "title": "Day 1 - <theme>",
      "duration_minutes": <30-60>,
      "exercises": [
        {{"name": "<exercise>", "sets": <sets>, "reps": "<reps or duration>", "focus": "<what it fixes>"}}
      ]
    }},
    {{"day": 2, "title": "Day 2 - <theme>", "duration_minutes": <30-60>, "exercises": [...]}},
    {{"day": 3, "title": "Day 3 - <theme>", "duration_minutes": <30-60>, "exercises": [...]}}
  ]
}}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800,
        temperature=0.4,
    )

    raw = response.choices[0].message.content.strip()
    clean = raw.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        clean = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

    return json.loads(clean)


def _fallback_result(sport: str) -> dict:
    """Return a safe fallback result when analysis fails."""
    return {
        "score":             52,
        "performance_label": "AVERAGE",
        "sport":             sport,
        "summary":           "We analyzed your video but had trouble processing the full analysis. Upload a clearer video for better results.",
        "form_issues":       ["Video quality may have affected analysis accuracy"],
        "coaching_tips":     [
            "Film from the side so your full body is visible",
            "Ensure good lighting for accurate pose detection",
            "Keep the camera steady throughout your movement",
        ],
        "strengths":         [],
        "metrics":           {"overall_score": 52, "technique": 50, "consistency": 50, "power_or_control": 50, "balance": 55, "follow_through": 50},
        "reps_completed":    0,
        "gpt_feedback":      "",
        "training_plan":     None,
        "annotated_frames":  [],
        "xp_earned":         50,
        "xp_breakdown":      [{"reason": "Uploaded a video", "xp": 50}],
        "total_xp":          50,
        "level":             1,
        "level_name":        "Rookie",
        "leveled_up":        False,
        "new_badges":        [],
        "xp_progress_pct":   25,
    }