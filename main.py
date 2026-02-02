from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
import uuid
from pathlib import Path
from datetime import datetime

app = FastAPI(title="Level Up Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
MAX_FILE_SIZE = 100 * 1024 * 1024
ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/mpeg",
    "video/quicktime",
    "video/x-msvideo",
    "video/webm"
}

os.makedirs(UPLOAD_DIR, exist_ok=True)

def validate_video_file(file: UploadFile) -> None:
    if file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_VIDEO_TYPES)}"
        )

def generate_safe_filename(original_filename: str) -> str:
    file_ext = Path(original_filename).suffix
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    return f"{timestamp}_{unique_id}{file_ext}"

def cleanup_old_files(days: int = 7) -> None:
    try:
        current_time = datetime.now().timestamp()
        for filename in os.listdir(UPLOAD_DIR):
            file_path = os.path.join(UPLOAD_DIR, filename)
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getmtime(file_path)
                if file_age > (days * 86400):
                    os.remove(file_path)
    except Exception as e:
        print(f"Cleanup error: {e}")

@app.get("/")
def root():
    return {
        "status": "Level Up backend running",
        "version": "1.0.0",
        "endpoints": {
            "upload": "/upload-video",
            "health": "/health"
        }
    }

@app.post("/upload-video")
async def upload_video(file: UploadFile = File(...)):
    try:
        validate_video_file(file)
        
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        safe_filename = generate_safe_filename(file.filename)
        file_path = os.path.join(UPLOAD_DIR, safe_filename)
        
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except IOError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save file: {str(e)}"
            )
        
        cleanup_old_files(days=7)
        
        analysis = {
            "sport": "basketball",
            "overall_score": 82,
            "positives": [
                "Good balance throughout the movement",
                "Controlled body position",
                "Stable stance during release"
            ],
            "focus_areas": [
                "Follow-through consistency",
                "Foot placement on release",
                "Elbow alignment"
            ],
            "training_plan": [
                "Form shooting: 50 reps per day",
                "Balance drills: 10 minutes per session",
                "Slow-motion shooting reps focusing on follow-through",
                "Wall sits for leg stability: 3 sets of 30 seconds"
            ],
            "analyzed_at": datetime.now().isoformat()
        }
        
        return {
            "success": True,
            "message": "Video uploaded and analyzed successfully",
            "filename": safe_filename,
            "original_filename": file.filename,
            "file_size": file_size,
            "analysis": analysis
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )
    finally:
        await file.close()

@app.get("/health")
def health():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "upload_dir_exists": os.path.exists(UPLOAD_DIR)
    }

@app.get("/stats")
def get_stats():
    try:
        files = os.listdir(UPLOAD_DIR)
        total_size = sum(
            os.path.getsize(os.path.join(UPLOAD_DIR, f)) 
            for f in files 
            if os.path.isfile(os.path.join(UPLOAD_DIR, f))
        )
        
        return {
            "total_files": len(files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "upload_dir": UPLOAD_DIR
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
