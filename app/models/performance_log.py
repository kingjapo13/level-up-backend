from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base


class PerformanceLog(Base):
    __tablename__ = "performance_logs"

    id = Column(Integer, primary_key=True, index=True)
    sport = Column(String, nullable=False)
    score = Column(Float, nullable=True)
    reps = Column(Integer, nullable=True)
    video_path = Column(String, nullable=True)
    metrics = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="performance_logs")

    athlete_id = Column(Integer, ForeignKey("athletes.id"), nullable=True)
athlete = relationship("Athlete", back_populates="performance_logs")