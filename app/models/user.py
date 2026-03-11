from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    device_token = Column(String, nullable=True)
    personality_mode = Column(String, default="supportive")

    subscription = relationship("Subscription", back_populates="user", uselist=False)
    athletes = relationship("Athlete", back_populates="owner")
    performance_logs = relationship("PerformanceLog", back_populates="user")
    sessions = relationship("Session", back_populates="user")