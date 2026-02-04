# main.py (root of your repo)
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
import uuid
from datetime import datetime
import cv2
import numpy as np
from mediapipe import solutions as mp_solutions  # ✅ Correct import

# ------------------ FastAPI ------------------
app = FastAPI(title="LevelUp Sports AI", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ------------------ MediaPipe Pose ------------------
mp_pose = mp_solutions.pose.Pose(
    static_image_mode=False,
    model_complexity=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

# ------------------ UTILITIES ------------------
def angle(a, b, c):
    a, b, c = np.array(a), np.array(b), np.array(c)
    ba, bc = a - b, c - b
    cos_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    return float(np.degrees(np.arccos(np.clip(cos_angle, -1, 1))))

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

# ------------------ ANALYSIS ------------------
def analyze(video_path, sport="basketball"):
    cap = cv2.VideoCapture(video_path)

    frame_skip = 5  # speed optimization
    frame_id = 0
    prev_wrist_y = None
    reps = 0
    rep_state = "down"

    frames = []
    elbow_angles = []

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
        res = mp_pose.process(rgb)

        if not res.pose_landmarks:
            continue

        lm = res.pose_landmarks.landmark

        shoulder = lm[mp_solutions.pose.PoseLandmark.RIGHT_SHOULDER]
        elbow = lm[mp_solutions.pose.PoseLandmark.RIGHT_ELBOW]
        wrist = lm[mp_solutions.pose.PoseLandmark.RIGHT_WRIST]
        hip = lm[mp_solutions.pose.PoseLandmark.RIGHT_HIP]
        knee = lm[mp_solutions.pose.PoseLandmark.RIGHT_KNEE]

        elbow_angle = angle(
            [shoulder.x, shoulder.y],
            [elbow.x, elbow.y],
            [wrist.x, wrist.y],
        )
        elbow_angles.append(elbow_angle)

        # ---- Rep detection ----
        if elbow_angle < 70:
            rep_state = "down"
        if elbow_angle > 140 and rep_state == "down":
            reps += 1
            rep_state = "up"

        # ---- Sport logic ----
        bad_form = False
        phase = None

        if sport == "basketball":
            _, good = basketball_shot(
                [elbow.x, elbow.y],
                [shoulder.x, shoulder.y],
                [wrist.x, wrist.y],
            )
            if not good:
                bad_form = True
                score -= 0.5

        elif sport == "golf":
            phase = golf_swing_phase(wrist.y, prev_wrist_y)

        prev_wrist_y = wrist.y

        frames.append({
            "frame": frame_id,
            "elbow_angle": round(elbow_angle, 1),
            "bad_form": bad_form,
            "phase": phase,
        })

    cap.release()

    avg_angle = np.mean(elbow_angles) if elbow_angles else 0
    if avg_angle < 90:
        feedback.append("Try keeping your elbow closer to 90° for better control.")
    if reps == 0:
        feedback.append("No clear reps detected. Make sure your full arm is visible.")

    return {
        "sport": sport,
        "overall_score": max(0, int(score)),
        "reps": reps,
        "coach_feedback": feedback or ["Solid mechanics overall."],
        "charts": {"elbow_angles": elbow_angles},
        "frames": frames,
        "analyzed_at": datetime.now().isoformat(),
    }

# ------------------ API ------------------
@app.post("/upload-video")
asyn

