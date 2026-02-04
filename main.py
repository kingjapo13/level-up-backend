from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import cv2
import numpy as np
import tempfile
import os

# ✅ MediaPipe import that WORKS on Render (Linux)
from mediapipe.python.solutions import pose as mp_pose

app = FastAPI()

# Allow frontend access later (Glide, web, mobile)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=1,
    enable_segmentation=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

@app.get("/")
def root():
    return {"status": "Level Up backend is running 🚀"}

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/analyze-video")
async def analyze_video(file: UploadFile = File(...)):
    # Save uploaded video temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(await file.read())
        video_path = tmp.name

    cap = cv2.VideoCapture(video_path)

    frame_count = 0
    landmarks_detected = 0

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break

        frame_count += 1
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)

        if results.pose_landmarks:
            landmarks_detected += 1

    cap.release()
    os.remove(video_path)

    return {
        "frames_processed": frame_count,
        "frames_with_pose": landmarks_detected,
        "pose_detection_rate": round(
            (landmarks_detected / frame_count) * 100, 2
        ) if frame_count > 0 else 0
    }


