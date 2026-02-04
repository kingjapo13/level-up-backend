from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
import uuid
from datetime import datetime

import cv2
import numpy as np

# ✅ CORRECT MediaPipe import (works on Render)
from mediapipe.python.solutions import pose as mp_pose

# -------------------- APP SETUP --------------------

app = FastAPI(title="LevelUp Sports AI", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# -------------------- MEDIAPIPE POSE --------------------

pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

# -------------------- UTILITIES --------------------

def calculate_angle(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    ba = a - b
    bc = c - b

    cosine = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    angle = np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))
    return float(angle)

# -------------------- SPORT LOGIC --------------------

def basketball_shot_feedback(shoulder, elbow, wrist):
    elbow_angle = calculate_angle(shoulder, elbow, wrist)
    good_form = 85 <= elbow_angle <= 110
    return elbow_angle, good_form

# -------------------- VIDEO ANALYSIS --------------------

def analyze_video(video_path: str, sport: str):
    cap = cv2.VideoCapture(video_path)

    frame_skip = 5
    frame_count = 0

    elbow_angles = []
    frames = []
    reps = 0
    rep_state = "down"
    score = 100

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        if frame_count % frame_skip != 0:
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)

        if not results.pose_landmarks:
            continue

        lm = results.pose_landmarks.landmark

        shoulder = lm[mp_pose.PoseLandmark.RIGHT_SHOULDER]
        elbow = lm[mp_pose.PoseLandmark.RIGHT_ELBOW]
        wrist = lm[mp_pose.PoseLandmark.RIGHT_WRIST]

        elbow_angle = calculate_angle(
            [shoulder.x, shoulder.y],
            [elbow.x, elbow.y],
            [wrist.x, wrist.y],
        )

        elbow_angles.append(elbow_angle)

        # ---- Rep counting ----
        if elbow_angle < 70:
            rep_state = "down"
        elif elbow_angle > 140 and rep_state == "down":
            reps += 1
            rep_state = "up"

        bad_form = False

        if sport == "basketball":
            _, good = basketball_shot_feedback(
                [shoulder.x, shoulder.y],
                [elbow.x, elbow.y],
                [wrist.x, wrist.y],
            )
            if not good:
                bad_form = True
                score -= 0.5

        frames.append({
            "frame": frame_count,
            "elbow_angle": round(elbow_angle, 1),
            "bad_form": bad_form
        })

    cap.release()

    avg_angle = np.mean(elbow_angles) if elbow_angles else 0
    feedback = []

    if avg_angle < 90:
        feedback.append("Try keeping your elbow closer to 90 degrees.")
    if reps == 0:
        feedback.append("No clear reps detected. Make sure your full arm is visible.")

    if not feedback:
        feedback.append("Great form overall. Keep it up!")

    return {
        "sport": sport,
        "overall_score": max(0, int(score)),
        "reps": reps,
        "coach_feedback": feedback,
        "charts": {
            "elbow_angles": elbow_angles
        },
        "frames": frames,
        "analyzed_at": datetime.now().isoformat()
    }

# -------------------- API ROUTES --------------------

@app.post("/upload-video")
async def upload_video(
    file: UploadFile = File(...),
    sport: str = Form("basketball"),
):
    if not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Only video files allowed")

    filename = f"{uuid.uuid4()}.mp4"
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    analysis = analyze_video(file_path, sport)

    return {
        "success": True,
        "analysis": analysis
    }

@app.get("/health")
def health_check():
    return {"status": "ok"}
