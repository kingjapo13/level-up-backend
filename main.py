from fastapi import FastAPI, UploadFile, File
import cv2
import mediapipe as mp
import numpy as np
import tempfile
import os
import math
import json

app = FastAPI()

mp_pose = mp.solutions.pose
pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=1,
    smooth_landmarks=True
)

# -------------------------
# Utility math
# -------------------------
def calculate_angle(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    ba = a - b
    bc = c - b

    cosine_angle = np.dot(ba, bc) / (
        np.linalg.norm(ba) * np.linalg.norm(bc)
    )
    angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))
    return math.degrees(angle)


def landmark_to_point(lm, w, h):
    return [lm.x * w, lm.y * h]


# -------------------------
# Core analyzer
# -------------------------
def analyze_video(video_path, mode="squat"):
    cap = cv2.VideoCapture(video_path)

    frame_count = 0
    rep_count = 0
    stage = None
    output_frames = []

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        # ⏩ FRAME SAMPLING (every 3rd frame)
        if frame_count % 3 != 0:
            continue

        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)

        if not results.pose_landmarks:
            continue

        lm = results.pose_landmarks.landmark

        # Key joints
        hip = landmark_to_point(lm[mp_pose.PoseLandmark.LEFT_HIP], w, h)
        knee = landmark_to_point(lm[mp_pose.PoseLandmark.LEFT_KNEE], w, h)
        ankle = landmark_to_point(lm[mp_pose.PoseLandmark.LEFT_ANKLE], w, h)

        shoulder = landmark_to_point(lm[mp_pose.PoseLandmark.LEFT_SHOULDER], w, h)
        elbow = landmark_to_point(lm[mp_pose.PoseLandmark.LEFT_ELBOW], w, h)
        wrist = landmark_to_point(lm[mp_pose.PoseLandmark.LEFT_WRIST], w, h)

        knee_angle = calculate_angle(hip, knee, ankle)
        hip_angle = calculate_angle(shoulder, hip, knee)
        elbow_angle = calculate_angle(shoulder, elbow, wrist)

        bad_form = False
        feedback = []

        # -------------------------
        # MODE LOGIC
        # -------------------------
        if mode == "squat":
            if knee_angle < 90:
                stage = "down"
            if knee_angle > 160 and stage == "down":
                rep_count += 1
                stage = "up"

            if hip_angle < 70:
                bad_form = True
                feedback.append("Chest leaning too far forward")

        elif mode == "pushup":
            if elbow_angle < 90:
                stage = "down"
            if elbow_angle > 160 and stage == "down":
                rep_count += 1
                stage = "up"

            if hip_angle < 150:
                bad_form = True
                feedback.append("Hips sagging")

        # -------------------------
        # Frame JSON output
        # -------------------------
        output_frames.append({
            "frame": frame_count,
            "angles": {
                "knee": round(knee_angle, 1),
                "hip": round(hip_angle, 1),
                "elbow": round(elbow_angle, 1)
            },
            "rep_count": rep_count,
            "bad_form": bad_form,
            "feedback": feedback,
            "landmarks": {
                "hip": hip,
                "knee": knee,
                "ankle": ankle,
                "shoulder": shoulder,
                "elbow": elbow,
                "wrist": wrist
            }
        })

    cap.release()

    return {
        "mode": mode,
        "total_reps": rep_count,
        "frames_analyzed": len(output_frames),
        "frames": output_frames
    }


# -------------------------
# API endpoint
# -------------------------
@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    mode: str = "squat"
):
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    result = analyze_video(tmp_path, mode)
    os.remove(tmp_path)

    return result


# -------------------------
# Health check
# -------------------------
@app.get("/")
def root():
    return {"status": "LevelUp backend running 🚀"}

