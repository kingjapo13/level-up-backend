from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.db.database import get_db
from app.models.athlete import Athlete
from app.models.user import User
from app.security import get_current_user

router = APIRouter(prefix="/athletes", tags=["Athletes"])


class AthleteCreate(BaseModel):
    name: str
    sport: Optional[str] = None
    age: Optional[int] = None


class AthleteOut(BaseModel):
    id: int
    name: str
    sport: Optional[str]
    age: Optional[int]
    owner_id: int

    class Config:
        from_attributes = True


@router.get("/", response_model=List[AthleteOut])
def list_athletes(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return db.query(Athlete).filter(Athlete.owner_id == user.id).all()


@router.post("/", response_model=AthleteOut)
def create_athlete(
    athlete: AthleteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    new_athlete = Athlete(
        name=athlete.name,
        sport=athlete.sport,
        age=athlete.age,
        owner_id=user.id,
    )
    db.add(new_athlete)
    db.commit()
    db.refresh(new_athlete)
    return new_athlete


@router.delete("/{athlete_id}")
def delete_athlete(
    athlete_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    athlete = db.query(Athlete).filter(
        Athlete.id == athlete_id, Athlete.owner_id == user.id
    ).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    db.delete(athlete)
    db.commit()
    return {"status": "deleted"}