from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.security import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.post("/register-device")
def register_device(
    token: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    user.device_token = token
    db.commit()
    return {"status": "device_registered"}