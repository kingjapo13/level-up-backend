from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from app.db.database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    tier = Column(String, default="trial", nullable=False)
    is_active = Column(Boolean, default=True)
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    trial_end = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="subscription")

    @property
    def is_trial(self):
        return self.tier == "trial"

    @property
    def trial_expired(self):
        if not self.is_trial:
            return False
        if self.trial_end is None:
            return False
        return datetime.utcnow() > self.trial_end

    @property
    def trial_days_remaining(self):
        if not self.is_trial or self.trial_end is None:
            return 0
        delta = self.trial_end - datetime.utcnow()
        return max(0, delta.days)

    @property
    def effective_tier(self):
        if self.is_trial and not self.trial_expired:
            return "pro"
        if self.is_trial and self.trial_expired:
            return "expired"
        return self.tier