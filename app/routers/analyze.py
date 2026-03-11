import logging

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Form
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.security import get_current_user
from services.analyze_service import analyze_video

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyze", tags=["Analyze"])


@router.post("/")
async def analyze(
    sport: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await analyze_video(file=file, sport=sport, db=db, user=user)

    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    return {"status": "success", "results": result}