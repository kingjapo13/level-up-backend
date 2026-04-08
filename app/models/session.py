from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, ForeignKey("athletes.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    sport = Column(String, nullable=True)
    score = Column(Float, nullable=True)
    video_path = Column(String, nullable=True)
    metrics = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    athlete = relationship("Athlete", back_populates="sessions")