# main.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
import uuid
from datetime import datetime
from collections import defaultdict

import cv2
import numpy as np

# ---- MediaPipe ----
import mediapipe as mp

mp_pose = mp.solutions.pose

# ---- FastAPI ----
app = FastAPI(title="LevelUp Sports AI", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---- MediaPipe Pose ----
pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

# ---- Parent Dashboard Data ----
# parent_id -> child_name -> list of analysis
parent_data = defaultdict(lambda: defaultdict(list))

# ------------------ UTILITIES ------------------
def angle(a, b, c):
    a, b, c = np.array(a), np.array(b), np.array(c)
    ba, bc = a - b, c - b
    cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    return float(np.degrees(np.arccos(np.clip(cos, -1, 1))))

# ------------------ SPORT LOGIC ------------------
def basketball_shot(elbow, shoulder, wrist):
    elbow_angle = angle(shoulder, elbow, wrist)
    good = 85 <= elbow_angle <= 110
    return elbow_angle, good

def golf_swing_phase(wrist_y, prev):
    if prev is None:
        return "setup"
    if wrist_y < prev - 0.02:
        return "backswing"
    if wrist_y > prev + 0.02:
        return "downswing"
    return "follow_through"

def soccer_kick(hip, knee, ankle):
    knee_angle = angle(hip, knee, ankle)
    good = 70 <= knee_angle <= 110
    return knee_angle, good

# ------------------ ANALYSIS ------------------
def analyze(video_path, sport="basketball"):
    cap = cv2.VideoCapture(video_path)

    frame_skip = 5
    frame_id = 0
    prev_wrist_y = None
    reps = 0
    rep_state = "down"

    frames = []
    angles = []

    score = 100
    feedback = []

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_id += 1
        if frame_id % frame_skip != 0:
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = pose.process(rgb)

        if not res.pose_landmarks:
            continue

        lm = res.pose_landmarks.landmark

        shoulder = lm[mp_pose.PoseLandmark.RIGHT_SHOULDER]
        elbow = lm[mp_pose.PoseLandmark.RIGHT_ELBOW]
        wrist = lm[mp_pose.PoseLandmark.RIGHT_WRIST]
        hip = lm[mp_pose.PoseLandmark.RIGHT_HIP]
        knee = lm[mp_pose.PoseLandmark.RIGHT_KNEE]
        ankle = lm[mp_pose.PoseLandmark.RIGHT_ANKLE]

        bad_form = False
        phase = None
        angle_val = None

        if sport == "basketball":
            angle_val, good = basketball_shot(
                [elbow.x, elbow.y],
                [shoulder.x, shoulder.y],
                [wrist.x, wrist.y],
            )
            if not good:
                bad_form = True
                score -= 0.5

        elif sport == "golf":
            angle_val = angle(shoulder.x, elbow.x, wrist.x)  # basic for charts
            phase = golf_swing_phase(wrist.y, prev_wrist_y)

        elif sport == "soccer":
            angle_val, good = soccer_kick(
                [hip.x, hip.y],
                [knee.x, knee.y],
                [ankle.x, ankle.y],
            )
            if not good:
                bad_form = True
                score -= 0.5

        prev_wrist_y = wrist.y
        angles.append(angle_val)

        # Simple rep detection (for basketball/golf)
        if angle_val is not None:
            if angle_val < 70:
                rep_state = "down"
            if angle_val > 140 and rep_state == "down":
                reps += 1
                rep_state = "up"

        frames.append({
            "frame": frame_id,
            "angle": round(angle_val, 1) if angle_val else None,
            "bad_form": bad_form,
            "phase": phase,
        })

    cap.release()

    avg_angle = np.mean(angles) if angles else 0

    if avg_angle < 90:
        feedback.append("Try keeping your angles closer to 90° for better control.")
    if reps == 0:
        feedback.append("No clear reps detected. Make sure your full limb is visible.")

    return {
        "sport": sport,
        "overall_score": max(0, int(score)),
        "reps": reps,
        "coach_feedback": feedback or ["Solid mechanics overall."],
        "charts": {"angles": angles},
        "frames": frames,
        "analyzed_at": datetime.now().isoformat(),
    }

# ------------------ API ------------------
@app.post("/upload-video")
async def upload_video(
    parent_id: str = Form(...),
    child_name: str = Form(...),
    file: UploadFile = File(...),
    sport: str = Form(...),
):
    if sport not in ["basketball", "golf", "soccer"]:
        raise HTTPException(400, "Sport must be basketball, golf, or soccer")
    if not file.content_type.startswith("video/"):
        raise HTTPException(400, "Video only")

    filename = f"{uuid.uuid4()}.mp4"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    result = analyze(path, sport)
    parent_data[parent_id][child_name].append(result)

    return {"success": True, "analysis": result}

@app.get("/parent-dashboard/{parent_id}/{child_name}")
def get_dashboard(parent_id: str, child_name: str):
    sessions = parent_data.get(parent_id, {}).get(child_name, [])
    if not sessions:
        return {"child_name": child_name, "total_sessions": 0, "progress": {}, "sessions": []}

    avg_score = sum(s["overall_score"] for s in sessions) / len(sessions)
    total_reps = sum(s["reps"] for s in sessions)

    progress = {"avg_score": avg_score, "total_reps": total_reps}

    return {
        "child_name": child_name,
        "total_sessions": len(sessions),
        "progress": progress,
        "sessions": sessions,
    }

@app.get("/health")
def health():
    return {"status": "ok"}


