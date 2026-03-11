from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from app.db.database import get_db
from app.models.performance_log import PerformanceLog
from app.models.user import User
from app.security import get_current_user

router = APIRouter(prefix="/logs", tags=["Performance Logs"])


class PerformanceLogOut(BaseModel):
    id: int
    sport: str
    score: Optional[float]
    reps: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=List[PerformanceLogOut])
def get_my_logs(
    sport: str = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(PerformanceLog).filter(PerformanceLog.user_id == user.id)
    if sport:
        query = query.filter(PerformanceLog.sport == sport)
    return query.order_by(PerformanceLog.created_at.desc()).limit(limit).all()