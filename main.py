from fastapi import FastAPI, UploadFile, File
import cv2
import numpy as np
from mediapipe import solutions
import tempfile

app = FastAPI()

# MediaPipe Pose (NEW API)
mp_pose = solutions.pose
pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=1,
    enable_segmentation=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# ---------- Utility Functions ----------

def calculate_angle(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - \
              np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = abs(radians * 180.0 / np.pi)

    if angle > 180:
        angle = 360 - angle

    return round(angle, 2)

def extract_landmark(landmarks, idx):
    lm = landmarks[idx]
    return [lm.x, lm.y]

# ---------- API Route ----------

@app.post("/analyze")
async def analyze_video(file: UploadFile = File(...)):
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.write(await file.read())

    cap = cv2.VideoCapture(temp_file.name)

    frame_results = []
    frame_count = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = pose.process(image)

        if result.pose_landmarks:
            lm = result.pose_landmarks.landmark

            hip = extract_landmark(lm, mp_pose.PoseLandmark.RIGHT_HIP)
            knee = extract_landmark(lm, mp_pose.PoseLandmark.RIGHT_KNEE)
            ankle = extract_landmark(lm, mp_pose.PoseLandmark.RIGHT_ANKLE)

            knee_angle = calculate_angle(hip, knee, ankle)

            frame_results.append({
                "frame": frame_count,
                "right_knee_angle": knee_angle
            })

        frame_count += 1

    cap.release()

    return {
        "frames_analyzed": frame_count,
        "pose_frames": len(frame_results),
        "data": frame_results
    }

@app.get("/")
def health():
    return {"status": "running"}

