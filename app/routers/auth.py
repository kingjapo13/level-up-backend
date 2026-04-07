import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from jose import jwt
from passlib.context import CryptContext
import os

from app.db.database import get_db
from app.models.user import User
from app.models.subscription import Subscription
from app.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY", "levelup-secret-key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "43200"))


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class PushTokenRequest(BaseModel):
    token: str


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


@router.post("/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user with a free trial subscription."""

    # Check existing username
    if db.query(User).filter(User.username == request.username).first():
        raise HTTPException(
            status_code=400,
            detail="Username already taken. Please choose a different one."
        )

    # Check existing email
    if db.query(User).filter(User.email == request.email).first():
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists."
        )

    # Create user
    user = User(
        username=request.username,
        email=request.email,
        hashed_password=hash_password(request.password),
    )
    db.add(user)
    db.flush()

    # Create 7-day trial subscription
    trial_end = datetime.utcnow() + timedelta(days=7)
    subscription = Subscription(
        user_id=user.id,
        tier="trial",
        trial_end=trial_end,
        is_active=True,
    )
    db.add(subscription)
    db.commit()

    logger.info(f"New user registered: {request.username} (trial until {trial_end.date()})")
    return {
        "message": "Account created successfully! Your 7-day free trial has started.",
        "username": user.username,
    }


@router.post("/token")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Login and get access token."""
    user = db.query(User).filter(User.username == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({"sub": user.username})
    logger.info(f"User logged in: {user.username}")

    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user.username,
    }


@router.get("/me")
def get_me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get current user profile."""
    subscription = user.subscription
    tier = subscription.effective_tier if subscription else "free"
    trial_days = None

    if subscription and subscription.tier == "trial" and subscription.trial_end:
        days = (subscription.trial_end - datetime.utcnow()).days
        trial_days = max(0, days)

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "tier": tier,
        "is_trial": tier == "trial",
        "trial_expired": tier == "expired",
        "trial_days_remaining": trial_days,
        "device_token": user.device_token,
    }


@router.post("/push-token")
def save_push_token(
    request: PushTokenRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Save user's Expo push notification token."""
    try:
        user.device_token = request.token
        db.commit()
        logger.info(f"Push token saved for user {user.id}: {request.token[:30]}...")
        return {"status": "ok", "message": "Push token saved"}
    except Exception as e:
        logger.error(f"Push token save error: {e}")
        raise HTTPException(status_code=500, detail="Could not save push token")


@router.post("/logout")
def logout(user: User = Depends(get_current_user)):
    """Logout endpoint — client should delete token."""
    logger.info(f"User logged out: {user.username}")
    return {"message": "Logged out successfully"}