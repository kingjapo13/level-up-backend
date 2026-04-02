import logging
from fastapi import APIRouter, File, UploadFile, Form, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.security import get_current_user
from services.analyze_service import analyze_video

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyze", tags=["Analyze"])


@router.post("/")
async def analyze(
    file: UploadFile = File(...),
    sport: str = Form("squat"),
    personality: str = Form("supportive"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Analyzes an uploaded video for athletic performance.
    Returns score, form issues, coaching tips, GPT feedback and training plan.
    """
    logger.info(
        f"Analysis request from user {user.id}: sport={sport}, "
        f"file={file.filename}, personality={personality}"
    )

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    allowed_types = {
        "video/mp4", "video/quicktime", "video/x-msvideo",
        "video/mpeg", "video/webm", "video/3gpp",
        "application/octet-stream",
    }
    if file.content_type and file.content_type not in allowed_types:
        logger.warning(f"Unexpected content type: {file.content_type}")

    try:
        result = await analyze_video(
            file=file,
            sport=sport,
            db=db,
            user=user,
            personality=personality,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis endpoint error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Analysis failed unexpectedly. Please try again."
        )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    logger.info(
        f"Analysis complete for user {user.id}: "
        f"score={result.get('score')}, sport={sport}"
    )

    return result