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

# -------------------------------
# ⚠️ MediaPipe Python version guard
# -------------------------------
if sys.version_info >= (3, 13):
    raise RuntimeError(
        "MediaPipe requires Python 3.10 or 3.11. "
        "Set .python-version to 3.10 or set PYTHON_VERSION=3.10.x in Render."
    )

import mediapipe as mp

# -------------------------------
# ⚙️ Performance tuning
# -------------------------------
FRAME_SKIP = 6        # Analyze 1 out of every 6 frames
MAX_FRAMES = 300     # Hard cap on analyzed frames
MIN_FRAMES = 40      # Minimum frames for valid analysis

# -------------------------------
# 🚀 App setup
# -------------------------------
app = FastAPI(title="Sports Coach AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB
os.makedirs(UPLOAD_DIR, exist_ok=True)

# -------------------------------
# 🧠 MediaPipe Pose
# -------------------------------
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=1,  # faster for deploy
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

# -------------------------------
# 📐 Helper functions
# -------------------------------
def calculate_angle(p1, p2, p3):
    a = np.array(p1, dtype=float)
    b = np.array(p2, dtype=float)
    c = np.array(p3, dtype=float)

    ba = a - b
    bc = c - b

    if np.linalg.norm(ba) == 0 or np.linalg.norm(bc) == 0:
        return 0.0

    cosine = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
    cosine = np.clip(cosine, -1.0, 1.0)

    return float(np.degrees(np.arccos(cosine)))


def calculate_balance(hip, knee, ankle):
    deviation = abs(hip[0] - knee[0]) + abs(knee[0] - ankle[0])
    return max(0.0, min(100.0, 100.0 - deviation * 500))


# -------------------------------
# 🎥 Video analysis
# -------------------------------
def analyze_body_movement(video_path: str, dominant_hand: str = "right"):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"error": "Could not open video"}

    angles = []
    balances = []
    velocities = []

    prev_wrist_y = None
    motion_detected = False

    frame_index = 0
    analyzed_frames = 0
    right_hand = dominant_hand.lower() == "right"

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_index += 1

            # ⏭️ Frame skipping
            if frame_index % FRAME_SKIP != 0:
                continue

            analyzed_frames += 1
            if analyzed_frames >= MAX_FRAMES:
                break

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb)

            if not results.pose_landmarks:
                continue

            lm = results.pose_landmarks.landmark

            if right_hand:
                shoulder = lm[mp_pose.PoseLandmark.RIGHT_SHOULDER]
                elbow = lm[mp_pose.PoseLandmark.RIGHT_ELBOW]
                wrist = lm[mp_pose.PoseLandmark.RIGHT_WRIST]
                hip = lm[mp_pose.PoseLandmark.RIGHT_HIP]
                knee = lm[mp_pose.PoseLandmark.RIGHT_KNEE]
                ankle = lm[mp_pose.PoseLandmark.RIGHT_ANKLE]
            else:
                shoulder = lm[mp_pose.PoseLandmark.LEFT_SHOULDER]
                elbow = lm[mp_pose.PoseLandmark.LEFT_ELBOW]
                wrist = lm[mp_pose.PoseLandmark.LEFT_WRIST]
                hip = lm[mp_pose.PoseLandmark.LEFT_HIP]
                knee = lm[mp_pose.PoseLandmark.LEFT_KNEE]
                ankle = lm[mp_pose.PoseLandmark.LEFT_ANKLE]

            angle = calculate_angle(
                [shoulder.x, shoulder.y],
                [elbow.x, elbow.y],
                [wrist.x, wrist.y],
            )
            angles.append(angle)

            balance = calculate_balance(
                [hip.x, hip.y],
                [knee.x, knee.y],
                [ankle.x, ankle.y],
            )
            balances.append(balance)

            if prev_wrist_y is not None:
                v = abs(wrist.y - prev_wrist_y)
                velocities.append(v)
                if v > 0.03:
                    motion_detected = True

            prev_wrist_y = wrist.y

    finally:
        cap.release()

    if analyzed_frames < MIN_FRAMES:
        return {
            "sport": "general",
            "overall_score": 0,
            "positives": [],
            "focus_areas": ["Not enough motion detected — try a longer clip."],
            "training_plan": ["Record 5–10 seconds with full body visible."],
            "metrics": {
                "frames_analyzed": analyzed_frames,
                "frame_sampling": f"1/{FRAME_SKIP}",
            },
            "analyzed_at": datetime.now().isoformat(),
        }

    return generate_feedback(
        angles, balances, velocities, motion_detected, analyzed_frames
    )


# -------------------------------
# 🧠 Feedback generation
# -------------------------------
def generate_feedback(angles, balances, velocities, motion_detected, frames):
    avg_angle = float(np.mean(angles)) if angles else 0.0
    avg_balance = float(np.mean(balances)) if balances else 0.0
    max_velocity = float(max(velocities)) if velocities else 0.0

    positives = []
    focus = []
    plan = []

    if 85 <= avg_angle <= 115:
        positives.append("Good arm angle for power and control.")
    else:
        focus.append(f"Arm angle avg {avg_angle:.1f}°. Aim for 90–110°.")
        plan.append("Wall drill: hold L-shape arm position.")

    if avg_balance > 70:
        positives.append("Good balance and body control.")
    else:
        focus.append("Balance could improve.")
        plan.append("Single-leg balance holds.")

    if motion_detected:
        positives.append("Clear movement detected.")
    else:
        focus.append("Motion too limited or slow.")
        plan.append("Practice smooth, full-range reps.")

    overall = int(
        min(
            100,
            (0.4 * avg_balance)
            + (40 * (1 - min(abs(100 - avg_angle) / 90, 1)))
            + (min(20, max_velocity * 200)),
        )
    )

    return {
        "sport": "general",
        "overall_score": overall,
        "positives": positives or ["Keep practicing for consistency."],
        "focus_areas": focus or ["Maintain fundamentals."],
        "training_plan": plan or ["Form drills daily."],
        "metrics": {
            "average_elbow_angle": round(avg_angle, 1),
            "average_balance_score": round(avg_balance, 1),
            "motion_detected": motion_detected,
            "frames_analyzed": frames,
            "frame_sampling": f"1/{FRAME_SKIP}",
        },
        "analyzed_at": datetime.now().isoformat(),
    }


# -------------------------------
# 📁 Utils
# -------------------------------
def generate_safe_filename(name: str) -> str:
    ext = Path(name).suffix or ".mp4"
    uid = str(uuid.uuid4())[:8]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{ts}_{uid}{ext}"


# -------------------------------
# 🌐 Routes
# -------------------------------
@app.get("/")
def root():
    return {"status": "Sports Coach AI running"}

@app.post("/upload-video")
async def upload_video(
    file: UploadFile = File(...),
    dominant_hand: str = Form("right"),
):
    if not file.content_type.startswith("video/"):
        raise HTTPException(400, "Only video files allowed")

    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)

    if size > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large")

    filename = generate_safe_filename(file.filename or "video.mp4")
    path = os.path.join(UPLOAD_DIR, filename)

    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    analysis = analyze_body_movement(path, dominant_hand)

    return {
        "success": True,
        "filename": filename,
        "analysis": analysis,
    }

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


