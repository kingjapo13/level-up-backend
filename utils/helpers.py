import os
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, List

logger = logging.getLogger(__name__)


def save_upload(file, directory: str = "uploads") -> str:
    os.makedirs(directory, exist_ok=True)
    ext = os.path.splitext(file.filename)[-1] or ".mp4"
    filename = f"{directory}/{uuid.uuid4()}{ext}"
    with open(filename, "wb") as buffer:
        import shutil
        shutil.copyfileobj(file.file, buffer)
    return filename


def delete_file(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logger.warning(f"Could not delete file {path}: {e}")


def start_of_week() -> datetime:
    return datetime.utcnow() - timedelta(days=7)


def safe_average(values: List[Optional[float]]) -> Optional[float]:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return round(sum(clean) / len(clean), 2)


def clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, value))


def get_tier(user) -> str:
    try:
        if user.subscription and user.subscription.is_active:
            return user.subscription.tier
    except AttributeError:
        pass
    return "free"