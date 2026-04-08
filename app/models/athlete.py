from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base


class Athlete(Base):
    __tablename__ = "athletes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    sport = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    location = Column(String, nullable=True)
    skill_level = Column(String, nullable=True)
    best_score = Column(Float, nullable=True)
    total_sessions = Column(Integer, default=0)
    bio = Column(String, nullable=True)
    looking_for = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship back to user — no back_populates to avoid circular issues
    user = relationship("User", foreign_keys=[user_id])