from sqlalchemy import Column, Integer, Float, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    video_path = Column(String, nullable=False)
    sport = Column(String, nullable=True)
    reps_completed = Column(Integer, default=0)
    score = Column(Float, default=0.0)
    feedback_summary = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="sessions")

    athlete_id = Column(Integer, ForeignKey("athletes.id"), nullable=True)
    athlete = relationship("Athlete", back_populates="sessions")