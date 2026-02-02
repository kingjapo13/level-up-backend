from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import threading

app = FastAPI(title="Level Up Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
RESULTS_DIR = "results"
MAX_FILE_SIZE = 100 * 1024 * 1024
ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/mpeg",
    "video/quicktime",
    "video/x-msvideo",
    "video/webm"
}

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# In-memory job maps (for demo only). Use a DB or persistent store in production.
JOB_STATUS: Dict[str, str] = {}
JOB_RESULTS: Dict[str, Dict[str, Any]] = {}

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

def process_video_worker(input_path: str, job_id: str, model_dir: str = None, dominant_hand: str = "right"):
    """
    Background worker that runs the actual analysis. It should produce:
      - annotated video
      - analysis JSON
    The concrete implementation should live in process_video.analyze_video(...) and return metadata (paths).
    """
    try:
        JOB_STATUS[job_id] = "processing"
        # Import here so heavy deps are only loaded in worker context
        try:
            from process_video import analyze_video
        except Exception as e:
            # If process_video is missing, mark error
            JOB_STATUS[job_id] = f"error: process_video module not found: {e}"
            return

        out_dir = os.path.join(RESULTS_DIR, job_id)
        os.makedirs(out_dir, exist_ok=True)

        # analyze_video should be implemented by you to run MediaPipe / classifier and return result paths
        result = analyze_video(input_path, output_dir=out_dir, model_dir=model_dir, dominant_hand=dominant_hand)

        # result expected to be a dict with keys like "annotated_video" and "analysis_json"
        JOB_RESULTS[job_id] = result or {}
        JOB_STATUS[job_id] = "done"
    except Exception as e:
        JOB_STATUS[job_id] = f"error: {e}"

@app.get("/")
def root():
    return {
        "status": "Level Up backend running",
        "version": "1.0.0",
        "endpoints": {
            "upload": "/upload-video",
            "health": "/health",
            "job_status": "/job/{job_id}/status",
            "job_result": "/job/{job_id}/result"
        }
    }

@app.post("/upload-video")
async def upload_video(file: UploadFile = File(...), background_tasks: BackgroundTasks = None, model_dir: str = None, dominant_hand: str = "right"):
    """
    Accept video upload, store it, then enqueue background processing.
    Returns a job_id which the client can poll via /job/{job_id}/status and retrieve results from /job/{job_id}/result when done.
    """
    try:
        validate_video_file(file)

        # measure size (seek/tell)
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

        # schedule background processing
        job_id = str(uuid.uuid4())
        JOB_STATUS[job_id] = "queued"
        JOB_RESULTS.pop(job_id, None)

        # Use FastAPI BackgroundTasks (runs after response) or start a thread as fallback
        if background_tasks is not None:
            background_tasks.add_task(process_video_worker, file_path, job_id, model_dir, dominant_hand)
        else:
            threading.Thread(target=process_video_worker, args=(file_path, job_id, model_dir, dominant_hand), daemon=True).start()

        # cleanup old uploads asynchronously (non-blocking)
        threading.Thread(target=cleanup_old_files, args=(7,), daemon=True).start()

        return {
            "success": True,
            "message": "Video uploaded and processing started",
            "job_id": job_id,
            "filename": safe_filename,
            "original_filename": file.filename,
            "file_size": file_size
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

@app.get("/job/{job_id}/status")
def job_status(job_id: str):
    return {"job_id": job_id, "status": JOB_STATUS.get(job_id, "not_found")}

@app.get("/job/{job_id}/result")
def job_result(job_id: str):
    """
    Return result metadata for a completed job. For simplicity this returns local paths.
    In production you should host result files (S3 / static file server) and return HTTP URLs.
    """
    status = JOB_STATUS.get(job_id, "not_found")
    if status == "not_found":
        raise HTTPException(status_code=404, detail="Job not found")
    if status.startswith("error"):
        raise HTTPException(status_code=500, detail=status)
    if status != "done":
        return {"job_id": job_id, "status": status}

    # job done -> return result metadata
    result = JOB_RESULTS.get(job_id, {})
    return {"job_id": job_id, "status": "done", "result": result}

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
