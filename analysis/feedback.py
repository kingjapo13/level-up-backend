import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def generate_feedback(
    reps: int,
    score: int,
    bad_form_issues: List[str],
    sport: Optional[str] = None,
    previous_score: Optional[int] = None,
) -> dict:
    if score >= 85:
        summary = "Excellent performance! Your form and consistency are on point."
    elif score >= 70:
        summary = "Great effort! You're developing solid technique."
    elif score >= 50:
        summary = "Good work. Focus on the form tips below to level up."
    else:
        summary = "Keep practicing — consistency and depth will improve your score."

    improvement = None
    if previous_score is not None:
        delta = score - previous_score
        if delta > 0:
            improvement = f"You improved by {delta} points since your last session! 📈"
        elif delta < 0:
            improvement = f"Score dropped by {abs(delta)} points — review your form tips."
        else:
            improvement = "Same score as last session — keep pushing!"

    coaching_tips = []
    for issue in bad_form_issues:
        coaching_tips.append({
            "issue": issue,
            "tip": _get_tip_for_issue(issue, sport),
        })

    feedback = {
        "summary": summary,
        "reps_completed": reps,
        "score": score,
        "form_issues": bad_form_issues,
        "coaching_tips": coaching_tips,
    }

    if improvement:
        feedback["improvement"] = improvement
    if sport:
        feedback["sport"] = sport

    return feedback


def _get_tip_for_issue(issue: str, sport: Optional[str]) -> str:
    issue_lower = issue.lower()

    sport_tips = {
        "basketball": {
            "not bending deep enough": "Bend your knees further before exploding upward.",
            "not fully extending": "Follow through fully — extend your arm completely.",
            "limited range of motion": "Work on your full shooting motion.",
        },
        "golf": {
            "not bending deep enough": "Maintain proper knee flex at address.",
            "not fully extending": "Complete your follow-through high over your shoulder.",
            "limited range of motion": "Focus on hip and shoulder rotation.",
        },
    }

    generic_tips = {
        "not bending deep enough": "Focus on bending the joint lower to achieve full depth.",
        "not fully extending": "Make sure to fully straighten the joint at the top of each rep.",
        "limited range of motion": "Work on flexibility to increase your movement range.",
    }

    if sport and sport.lower() in sport_tips:
        for key, tip in sport_tips[sport.lower()].items():
            if key in issue_lower:
                return tip

    for key, tip in generic_tips.items():
        if key in issue_lower:
            return tip

    return "Focus on controlled, deliberate movement throughout the full range of motion."