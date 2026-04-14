import logging
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

LEVELS = [
    {"level": 1,  "name": "Rookie",     "xp_required": 0},
    {"level": 2,  "name": "Beginner",   "xp_required": 200},
    {"level": 3,  "name": "Amateur",    "xp_required": 500},
    {"level": 4,  "name": "Competitor", "xp_required": 1000},
    {"level": 5,  "name": "Athlete",    "xp_required": 2000},
    {"level": 6,  "name": "Pro",        "xp_required": 3500},
    {"level": 7,  "name": "Elite",      "xp_required": 5500},
    {"level": 8,  "name": "Champion",   "xp_required": 8000},
    {"level": 9,  "name": "Legend",     "xp_required": 12000},
    {"level": 10, "name": "GOAT",       "xp_required": 20000},
]

BADGES = {
    "first_upload": {
        "id": "first_upload",
        "name": "First Upload",
        "emoji": "🏆",
        "description": "Uploaded your first training video",
        "color": "#FFD700",
    },
    "perfect_form": {
        "id": "perfect_form",
        "name": "Perfect Form",
        "emoji": "🎯",
        "description": "Scored 90+ with no form issues",
        "color": "#00FF88",
    },
    "consistency_king": {
        "id": "consistency_king",
        "name": "Consistency King",
        "emoji": "👑",
        "description": "Maintained a 7-day training streak",
        "color": "#FFD700",
    },
    "on_fire": {
        "id": "on_fire",
        "name": "On Fire",
        "emoji": "🔥",
        "description": "Uploaded 3 videos in one week",
        "color": "#FF6B35",
    },
    "most_improved": {
        "id": "most_improved",
        "name": "Most Improved",
        "emoji": "📈",
        "description": "Improved your score by 20+ points",
        "color": "#3498DB",
    },
    "grinder": {
        "id": "grinder",
        "name": "Grinder",
        "emoji": "⚡",
        "description": "Completed 10 training sessions",
        "color": "#9B59B6",
    },
    "all_star": {
        "id": "all_star",
        "name": "All-Star",
        "emoji": "🌟",
        "description": "Reached Level 5",
        "color": "#F1C40F",
    },
    "goat": {
        "id": "goat",
        "name": "G.O.A.T.",
        "emoji": "🐐",
        "description": "Reached Level 10 — Greatest of All Time",
        "color": "#00FF88",
    },
}


def get_level_info(xp: int) -> dict:
    """Get current level info based on XP."""
    current_level = LEVELS[0]
    next_level = LEVELS[1] if len(LEVELS) > 1 else None

    for i, level in enumerate(LEVELS):
        if xp >= level["xp_required"]:
            current_level = level
            next_level = LEVELS[i + 1] if i + 1 < len(LEVELS) else None

    xp_for_current = current_level["xp_required"]
    xp_for_next = next_level["xp_required"] if next_level else current_level["xp_required"]
    xp_in_level = xp - xp_for_current
    xp_needed = xp_for_next - xp_for_current
    progress_pct = round((xp_in_level / xp_needed * 100) if xp_needed > 0 else 100, 1)

    return {
        "level": current_level["level"],
        "level_name": current_level["name"],
        "xp": xp,
        "xp_for_current_level": xp_for_current,
        "xp_for_next_level": xp_for_next,
        "xp_in_level": xp_in_level,
        "xp_needed_for_next": max(0, xp_for_next - xp),
        "progress_pct": progress_pct,
        "is_max_level": next_level is None,
        "next_level_name": next_level["name"] if next_level else None,
    }


def calculate_xp_for_session(
    score: float,
    form_issues: list,
    is_personal_best: bool,
    streak: int,
    total_sessions: int,
) -> dict:
    """Calculate XP earned for a training session."""
    xp_breakdown = []
    total_xp = 0

    # Base XP for uploading
    xp_breakdown.append({"reason": "Uploaded a video", "xp": 50})
    total_xp += 50

    # Score-based XP
    if score >= 90:
        xp_breakdown.append({"reason": "Score 90+ 🔥", "xp": 100})
        total_xp += 100
    elif score >= 80:
        xp_breakdown.append({"reason": "Score 80+", "xp": 50})
        total_xp += 50
    elif score >= 70:
        xp_breakdown.append({"reason": "Score 70+", "xp": 25})
        total_xp += 25

    # Clean form bonus
    if not form_issues:
        xp_breakdown.append({"reason": "Perfect form! No issues", "xp": 30})
        total_xp += 30

    # Personal best bonus
    if is_personal_best:
        xp_breakdown.append({"reason": "New personal best! 🏆", "xp": 100})
        total_xp += 100

    # Streak bonuses
    if streak == 7:
        xp_breakdown.append({"reason": "7-day streak bonus 👑", "xp": 200})
        total_xp += 200
    elif streak == 3:
        xp_breakdown.append({"reason": "3-day streak bonus 🔥", "xp": 75})
        total_xp += 75

    # Milestone sessions
    if total_sessions == 1:
        xp_breakdown.append({"reason": "First session ever! 🎉", "xp": 100})
        total_xp += 100
    elif total_sessions == 10:
        xp_breakdown.append({"reason": "10 sessions milestone ⚡", "xp": 150})
        total_xp += 150
    elif total_sessions == 25:
        xp_breakdown.append({"reason": "25 sessions milestone 🌟", "xp": 250})
        total_xp += 250
    elif total_sessions == 50:
        xp_breakdown.append({"reason": "50 sessions milestone 🏆", "xp": 500})
        total_xp += 500

    return {"total_xp": total_xp, "breakdown": xp_breakdown}


def check_new_badges(
    game_profile,
    score: float,
    form_issues: list,
    streak: int,
    total_sessions: int,
    improvement: float,
) -> list:
    """Check which new badges the user has earned."""
    existing_badges = set(game_profile.badges or [])
    new_badges = []

    # First upload
    if total_sessions >= 1 and "first_upload" not in existing_badges:
        new_badges.append("first_upload")

    # Perfect form
    if score >= 90 and not form_issues and "perfect_form" not in existing_badges:
        new_badges.append("perfect_form")

    # Consistency King — 7 day streak
    if streak >= 7 and "consistency_king" not in existing_badges:
        new_badges.append("consistency_king")

    # On Fire — 3 uploads in a week (use total sessions as proxy)
    if total_sessions >= 3 and "on_fire" not in existing_badges:
        new_badges.append("on_fire")

    # Most improved
    if improvement >= 20 and "most_improved" not in existing_badges:
        new_badges.append("most_improved")

    # Grinder — 10 sessions
    if total_sessions >= 10 and "grinder" not in existing_badges:
        new_badges.append("grinder")

    # All-Star — Level 5
    if game_profile.level >= 5 and "all_star" not in existing_badges:
        new_badges.append("all_star")

    # GOAT — Level 10
    if game_profile.level >= 10 and "goat" not in existing_badges:
        new_badges.append("goat")

    return new_badges


def award_xp(
    user_id: int,
    db: Session,
    score: float,
    form_issues: list,
    is_personal_best: bool,
    streak: int,
    total_sessions: int,
    improvement: float = 0,
) -> dict:
    """Award XP and badges after a session. Returns XP earned and new badges."""
    try:
        from app.models.gamification import UserGameProfile

        # Get or create game profile
        game_profile = db.query(UserGameProfile).filter(
            UserGameProfile.user_id == user_id
        ).first()

        if not game_profile:
            game_profile = UserGameProfile(user_id=user_id, xp=0, level=1, badges=[])
            db.add(game_profile)
            db.flush()

        # Calculate XP
        xp_result = calculate_xp_for_session(
            score=score,
            form_issues=form_issues,
            is_personal_best=is_personal_best,
            streak=streak,
            total_sessions=total_sessions,
        )

        old_level = game_profile.level
        old_xp = game_profile.xp

        # Update XP
        game_profile.xp += xp_result["total_xp"]
        game_profile.total_xp_earned += xp_result["total_xp"]

        # Update level
        level_info = get_level_info(game_profile.xp)
        game_profile.level = level_info["level"]

        # Check badges
        new_badge_ids = check_new_badges(
            game_profile=game_profile,
            score=score,
            form_issues=form_issues,
            streak=streak,
            total_sessions=total_sessions,
            improvement=improvement,
        )

        leveled_up = game_profile.level > old_level

        if new_badge_ids:
            current_badges = list(game_profile.badges or [])
            current_badges.extend(new_badge_ids)
            game_profile.badges = current_badges

        db.commit()

        new_badges_data = [BADGES[bid] for bid in new_badge_ids if bid in BADGES]

        logger.info(
            f"XP awarded to user {user_id}: +{xp_result['total_xp']} XP, "
            f"level {game_profile.level}, badges: {new_badge_ids}"
        )

        return {
            "xp_earned": xp_result["total_xp"],
            "xp_breakdown": xp_result["breakdown"],
            "total_xp": game_profile.xp,
            "level": game_profile.level,
            "level_name": level_info["level_name"],
            "leveled_up": leveled_up,
            "new_level_name": level_info["level_name"] if leveled_up else None,
            "new_badges": new_badges_data,
            "progress_pct": level_info["progress_pct"],
            "xp_needed_for_next": level_info["xp_needed_for_next"],
        }

    except Exception as e:
        logger.error(f"XP award error: {e}", exc_info=True)
        return {
            "xp_earned": 0,
            "xp_breakdown": [],
            "total_xp": 0,
            "level": 1,
            "level_name": "Rookie",
            "leveled_up": False,
            "new_badges": [],
            "progress_pct": 0,
            "xp_needed_for_next": 200,
        }