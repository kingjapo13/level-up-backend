from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from app.db.database import get_db
from app.models.user import User
from app.models.athlete_profile import AthleteProfile
from app.models.performance_log import PerformanceLog
from app.security import get_current_user
from services.subscription_service import has_feature

router = APIRouter(prefix="/athletes", tags=["Athletes"])

SKILL_LEVELS = {
    "beginner": (0, 50),
    "intermediate": (51, 70),
    "advanced": (71, 85),
    "elite": (86, 100),
}


def score_to_skill(score: float) -> str:
    for level, (low, high) in SKILL_LEVELS.items():
        if low <= score <= high:
            return level
    return "beginner"


class AthleteProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    age: Optional[int] = None
    location: Optional[str] = None
    primary_sport: Optional[str] = None
    secondary_sports: Optional[str] = None
    bio: Optional[str] = None
    looking_for: Optional[str] = None
    is_visible: Optional[bool] = None


@router.get("/me")
def get_my_profile(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = db.query(AthleteProfile).filter(
        AthleteProfile.user_id == user.id
    ).first()

    if not profile:
        return {"profile": None}

    return {"profile": _format_profile(profile)}


@router.post("/me")
def create_or_update_profile(
    data: AthleteProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not has_feature(user, "athlete_matching"):
        raise HTTPException(
            status_code=403,
            detail="Athlete matching requires an Elite subscription.",
        )

    # Get user's avg score
    logs = db.query(PerformanceLog).filter(
        PerformanceLog.user_id == user.id
    ).all()
    scores = [l.score for l in logs if l.score]
    avg_score = sum(scores) / len(scores) if scores else None
    skill_level = score_to_skill(avg_score) if avg_score else "beginner"

    profile = db.query(AthleteProfile).filter(
        AthleteProfile.user_id == user.id
    ).first()

    if not profile:
        profile = AthleteProfile(user_id=user.id)
        db.add(profile)

    if data.display_name is not None:
        profile.display_name = data.display_name
    if data.age is not None:
        profile.age = data.age
    if data.location is not None:
        profile.location = data.location
    if data.primary_sport is not None:
        profile.primary_sport = data.primary_sport
    if data.secondary_sports is not None:
        profile.secondary_sports = data.secondary_sports
    if data.bio is not None:
        profile.bio = data.bio
    if data.looking_for is not None:
        profile.looking_for = data.looking_for
    if data.is_visible is not None:
        profile.is_visible = data.is_visible

    profile.avg_score = avg_score
    profile.skill_level = skill_level
    profile.total_sessions = len(logs)

    db.commit()
    db.refresh(profile)

    return {"profile": _format_profile(profile)}


@router.get("/match")
def find_matches(
    sport: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not has_feature(user, "athlete_matching"):
        raise HTTPException(
            status_code=403,
            detail="Athlete matching requires an Elite subscription.",
        )

    my_profile = db.query(AthleteProfile).filter(
        AthleteProfile.user_id == user.id
    ).first()

    if not my_profile:
        raise HTTPException(
            status_code=400,
            detail="Please set up your athlete profile first.",
        )

    # Find athletes at similar skill level
    query = db.query(AthleteProfile).filter(
        AthleteProfile.user_id != user.id,
        AthleteProfile.is_visible == True,
        AthleteProfile.skill_level == my_profile.skill_level,
    )

    if sport:
        query = query.filter(AthleteProfile.primary_sport == sport)
    elif my_profile.primary_sport:
        query = query.filter(
            AthleteProfile.primary_sport == my_profile.primary_sport
        )

    matches = query.limit(20).all()

    return {
        "my_skill_level": my_profile.skill_level,
        "my_sport": my_profile.primary_sport,
        "matches": [_format_profile(m) for m in matches],
        "total": len(matches),
    }


@router.get("/leaderboard")
def get_leaderboard(
    sport: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not has_feature(user, "athlete_matching"):
        raise HTTPException(
            status_code=403,
            detail="Leaderboard requires an Elite subscription.",
        )

    query = db.query(AthleteProfile).filter(
        AthleteProfile.is_visible == True,
        AthleteProfile.avg_score != None,
    )

    if sport:
        query = query.filter(AthleteProfile.primary_sport == sport)

    athletes = query.order_by(AthleteProfile.avg_score.desc()).limit(50).all()

    return {
        "leaderboard": [_format_profile(a, show_rank=True) for i, a in enumerate(athletes)],
        "total": len(athletes),
    }


def _format_profile(profile: AthleteProfile, show_rank: bool = False) -> dict:
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "display_name": profile.display_name or f"Athlete {profile.user_id}",
        "age": profile.age,
        "location": profile.location,
        "primary_sport": profile.primary_sport,
        "secondary_sports": profile.secondary_sports,
        "skill_level": profile.skill_level,
        "avg_score": round(profile.avg_score, 1) if profile.avg_score else None,
        "total_sessions": profile.total_sessions,
        "bio": profile.bio,
        "looking_for": profile.looking_for,
        "is_visible": profile.is_visible,
    }