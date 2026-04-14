import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.security import get_current_user
from services.xp_service import get_level_info, BADGES, LEVELS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gamification", tags=["Gamification"])


@router.get("/profile")
def get_game_profile(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get user's XP, level, and badges."""
    try:
        from app.models.gamification import UserGameProfile

        game_profile = db.query(UserGameProfile).filter(
            UserGameProfile.user_id == user.id
        ).first()

        if not game_profile:
            return {
                "xp": 0,
                "level": 1,
                "level_name": "Rookie",
                "badges": [],
                "total_xp_earned": 0,
                "progress_pct": 0,
                "xp_needed_for_next": 200,
                "next_level_name": "Beginner",
                "level_info": get_level_info(0),
                "all_badges": list(BADGES.values()),
                "levels": LEVELS,
            }

        level_info = get_level_info(game_profile.xp)
        earned_badge_ids = set(game_profile.badges or [])

        badges_data = []
        for badge_id, badge in BADGES.items():
            badges_data.append({
                **badge,
                "earned": badge_id in earned_badge_ids,
            })

        return {
            "xp": game_profile.xp,
            "level": game_profile.level,
            "level_name": level_info["level_name"],
            "badges": [b for b in badges_data if b["earned"]],
            "all_badges": badges_data,
            "total_xp_earned": game_profile.total_xp_earned,
            "progress_pct": level_info["progress_pct"],
            "xp_needed_for_next": level_info["xp_needed_for_next"],
            "next_level_name": level_info["next_level_name"],
            "level_info": level_info,
            "levels": LEVELS,
        }

    except Exception as e:
        logger.error(f"Game profile error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))