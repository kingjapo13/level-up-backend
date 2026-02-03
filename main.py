# main.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
import uuid
from pathlib import Path
from datetime import datetime
import sys
import cv2
import numpy as np

# MediaPipe does not support Python 3.13+; require 3.10 or 3.11 for deploy
if sys.version_info >= (3, 13):
    raise RuntimeError(
        "MediaPipe requires Python 3.10 or 3.11. "
        "Set .python-version to '3.10' or set PYTHON_VERSION=3.10.14 in your Render environment."
    )

import mediapipe as mp

app = FastAPI(title="Sports Coach AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Initialize MediaPipe Pose (lazy per-request is optional; module-level is fine for deploy)
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=1,  # 1 = faster, better for deploy; use 2 for higher accuracy
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)


def calculate_angle(point1, point2, point3):
    """Calculate angle at point2 between point1-point2-point3 (degrees)."""
    a = np.array(point1, dtype=float)
    b = np.array(point2, dtype=float)
    c = np.array(point3, dtype=float)
    ba = a - b
    bc = c - b
    n_ba = np.linalg.norm(ba)
    n_bc = np.linalg.norm(bc)
    if n_ba == 0 or n_bc == 0:
        return 0.0
    cosine = np.dot(ba, bc) / (n_ba * n_bc)
    cosine = np.clip(cosine, -1.0, 1.0)
    return float(np.degrees(np.arccos(cosine)))


def calculate_balance(hip, knee, ankle):
    """Balance score from hip-knee-ankle alignment (0-100)."""
    deviation = abs(hip[0] - knee[0]) + abs(knee[0] - ankle[0])
    return max(0.0, min(100.0, 100.0 - (deviation * 500)))


def analyze_body_movement(video_path: str, dominant_hand: str = "right"):
    """
    Analyze body movements in a video: pose, angles, balance, motion.
    Returns feedback suitable for any sport (shooting, throwing, swinging, etc.).
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {
            "error": "Could not open video file",
            "sport": "general",
            "overall_score": 0,
            "positives": [],
            "focus_areas": ["Video file could not be read. Try another format (e.g. MP4)."],
            "training_plan": [],
            "metrics": {},
            "analyzed_at": datetime.now().isoformat(),
        }

    angles = []
    balance_scores = []
    velocities = []
    frame_count = 0
    prev_wrist_y = None
    motion_detected = False
    right_used = dominant_hand.lower() == "right"

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb_frame)

            velocity = 0.0
            if results.pose_landmarks:
                landmarks = results.pose_landmarks.landmark

                if right_used:
                    shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
                    elbow = landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW]
                    wrist = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST]
                    hip = landmarks[mp_pose.PoseLandmark.RIGHT_HIP]
                    knee = landmarks[mp_pose.PoseLandmark.RIGHT_KNEE]
                    ankle = landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE]
                else:
                    shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
                    elbow = landmarks[mp_pose.PoseLandmark.LEFT_ELBOW]
                    wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST]
                    hip = landmarks[mp_pose.PoseLandmark.LEFT_HIP]
                    knee = landmarks[mp_pose.PoseLandmark.LEFT_KNEE]
                    ankle = landmarks[mp_pose.PoseLandmark.LEFT_ANKLE]

                elbow_angle = calculate_angle(
                    [shoulder.x, shoulder.y],
                    [elbow.x, elbow.y],
                    [wrist.x, wrist.y],
                )
                angles.append(elbow_angle)

                balance_score = calculate_balance(
                    [hip.x, hip.y], [knee.x, knee.y], [ankle.x, ankle.y]
                )
                balance_scores.append(balance_score)

                if prev_wrist_y is not None:
                    velocity = abs(wrist.y - prev_wrist_y)
                    velocities.append(velocity)
                    if velocity > 0.03:
                        motion_detected = True
                prev_wrist_y = wrist.y
    finally:
        cap.release()

    analysis = generate_feedback(
        angles, balance_scores, velocities, motion_detected, frame_count
    )
    return analysis


def generate_feedback(angles, balance_scores, velocities, motion_detected, frame_count):
    """Generate coaching feedback from pose metrics."""
    avg_angle = float(np.mean(angles)) if angles else 0.0
    avg_balance = float(np.mean(balance_scores)) if balance_scores else 0.0
    max_velocity = float(max(velocities)) if velocities else 0.0

    positives = []
    focus_areas = []
    training_plan = []

    # Elbow angle (ideal 90–110 for many sports)
    if angles:
        if 85 <= avg_angle <= 115:
            positives.append("Good arm angle — elbow in a strong position for power and control.")
        else:
            focus_areas.append(
                f"Arm angle averaging {avg_angle:.1f}° — aim for 90–110° for most throws/shots."
            )
            training_plan.append("Wall drill: practice L-shape arm position and hold.")

    # Balance
    if balance_scores:
        if avg_balance > 70:
            positives.append("Solid balance and body control during the movement.")
        else:
            focus_areas.append("Balance could improve — try to reduce sway and stay stable.")
            training_plan.append("Single-leg balance: 3 sets of 30 seconds each.")
            training_plan.append("Box step-ups or low jumps for stability.")

    # Motion
    if motion_detected:
        if max_velocity > 0.06:
            positives.append("Clear motion detected with good follow-through.")
        else:
            focus_areas.append("Motion is a bit slow or stiff — focus on smooth, full extension.")
            training_plan.append("Practice full range of motion with a slow, controlled tempo.")
    else:
        focus_areas.append("No clear throwing/shooting/swing motion detected — ensure full body is in frame and you perform the movement.")
        training_plan.append("Record again with full body visible and one clear rep of the movement.")

    # Overall score (0–100)
    angle_score = 40 * (1.0 - min(abs(100 - avg_angle) / 90, 1.0)) if angles else 20
    balance_component = 0.4 * avg_balance if balance_scores else 20
    motion_component = min(20, max_velocity * 200) if motion_detected else 0
    overall_score = int(min(100, angle_score + balance_component + motion_component))
    overall_score = max(0, overall_score)

    return {
        "sport": "general",
        "overall_score": overall_score,
        "positives": positives if positives else ["Keep practicing — consistency will improve form."],
        "focus_areas": focus_areas if focus_areas else ["Continue working on fundamentals."],
        "training_plan": training_plan if training_plan else ["Form drills: 2–3 sets of 10–15 reps daily."],
        "metrics": {
            "average_elbow_angle": round(avg_angle, 1),
            "average_balance_score": round(avg_balance, 1),
            "motion_detected": motion_detected,
            "frames_analyzed": frame_count,
            "landmark_frames": len(angles),
        },
        "analyzed_at": datetime.now().isoformat(),
    }


def generate_safe_filename(original_filename: str) -> str:
    ext = Path(original_filename).suffix or ".mp4"
    if ext.lower() not in (".mp4", ".mov", ".avi", ".webm", ".mkv"):
        ext = ".mp4"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    return f"{timestamp}_{unique_id}{ext}"


@app.get("/")
def root():
    return {
        "status": "Sports Coach AI running",
        "version": "1.0.0",
        "supported_sports": ["general"],
        "endpoints": {
            "upload": "/upload-video",
            "health": "/health",
        },
    }


@app.post("/upload-video")
async def upload_video(
    file: UploadFile = File(...),
    dominant_hand: str = Form("right"),
):
    try:
        if not file.content_type or not file.content_type.startswith("video/"):
            raise HTTPException(status_code=400, detail="Only video files are allowed.")

        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max size: {MAX_FILE_SIZE // (1024*1024)} MB",
            )

        safe_filename = generate_safe_filename(file.filename or "video")
        file_path = os.path.join(UPLOAD_DIR, safe_filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        analysis = analyze_body_movement(file_path, dominant_hand=dominant_hand)

        return {
            "success": True,
            "message": "Video analyzed successfully",
            "filename": safe_filename,
            "file_size": file_size,
            "analysis": analysis,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")
    finally:
        await file.close()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
    }

