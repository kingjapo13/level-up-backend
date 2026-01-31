# Add file validation
if not file.content_type.startswith('video/'):
    raise HTTPException(400, "Only video files allowed")

# Sanitize filename
import uuid
safe_filename = f"{uuid.uuid4()}_{file.filename}"

# Add error handling
try:
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
except Exception as e:
    raise HTTPException(500, f"Upload failed: {str(e)}")
The code will run and handle basic video uploads, but needs hardening for production use.can you make the whole code with your improvements11:54 AMpython# main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
import uuid
from pathlib import Path
from datetime import datetime

# Create the FastAPI app
app = FastAPI(title="Level Up Backend", version="1.0.0")

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
UPLOAD_DIR = "uploads"
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB limit
ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/mpeg",
    "video/quicktime",
    "video/x-msvideo",
    "video/webm"
}

# Create upload directory
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Helper function to validate file
def validate_video_file(file: UploadFile) -> None:
    """Validate uploaded file is a video and within size limits"""
    if file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_VIDEO_TYPES)}"
        )

# Helper function to generate safe filename
def generate_safe_filename(original_filename: str) -> str:
    """Generate a safe, unique filename"""
    # Get file extension
    file_ext = Path(original_filename).suffix
    # Create unique filename with timestamp and UUID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    return f"{timestamp}_{unique_id}{file_ext}"

# Helper function to cleanup old files (optional)
def cleanup_old_files(days: int = 7) -> None:
    """Remove files older than specified days"""
    try:
        current_time = datetime.now().timestamp()
        for filename in os.listdir(UPLOAD_DIR):
            file_path = os.path.join(UPLOAD_DIR, filename)
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getmtime(file_path)
                if file_age > (days * 86400):  # days to seconds
                    os.remove(file_path)
    except Exception as e:
        print(f"Cleanup error: {e}")

# Root endpoint — check if backend is live
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

# Upload video endpoint
@app.post("/upload-video")
async def upload_video(file: UploadFile = File(...)):
    try:
        # Validate file type
        validate_video_file(file)
        
        # Check file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # Generate safe filename
        safe_filename = generate_safe_filename(file.filename)
        file_path = os.path.join(UPLOAD_DIR, safe_filename)
        
        # Save file with error handling
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except IOError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save file: {str(e)}"
            )
        
        # Optional: Cleanup old files
        cleanup_old_files(days=7)
        
        # TODO: Replace with actual AI analysis
        # This is where you'd integrate your video analysis model
        analysis = {
            "summary": "Good balance and posture",
            "strengths": ["Stable stance", "Smooth motion"],
            "improvements": ["Follow-through consistency"],
            "score": 82,
            "analyzed_at": datetime.now().isoformat()
        }
        
        # Return success response
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
        # Clean up file handle
        await file.close()

# Health check endpoint
@app.get("/health")
def health():
    """Health check endpoint for monitoring"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "upload_dir_exists": os.path.exists(UPLOAD_DIR)
    }

# Optional: Get upload statistics
@app.get("/stats")
def get_stats():
    """Get statistics about uploaded files"""
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
