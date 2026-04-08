from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    device_token = Column(String, nullable=True)
    personality_mode = Column(String, default="supportive", nullable=True)
    age = Column(Integer, nullable=True)
    location = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    subscription = relationship(
        "Subscription",
        back_populates="user",
        uselist=False,
        lazy="select",
    )
    performance_logs = relationship(
        "PerformanceLog",
        back_populates="user",
        lazy="select",
    )
    athletes = relationship(
        "Athlete",
        back_populates="user",
        uselist=False,
        lazy="select",
    )
    athlete_profile = relationship(
        "AthleteProfile",
        back_populates="user",
        uselist=False,
        lazy="select",
    )