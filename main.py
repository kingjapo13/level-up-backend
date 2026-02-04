from fastapi import FastAPI, UploadFile, File, HTTPException
import cv2
import numpy as np
import tempfile
import mediapipe as mp

app = FastAPI(title="LevelUp Sports AI")

mp_pose = mp.solutions.pose
pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# ----------------- UTILITIES -----------------

def angle(a, b, c):
    a, b, c = map(np.array, (a, b, c))
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - \
              np.arctan2(a[1]-b[1], a[0]-b[0])
    deg = abs(radians * 180 / np.pi)
    return 360 - deg if deg > 180 else deg

def lm(landmarks, idx):
    p = landmarks[idx]
    return [p.x, p.y]

# ----------------- ANALYSIS -----------------

@app.post("/analyze")
async def analyze_video(file: UploadFile = File(...)):
    if not file.content_type.startswith("video"):
        raise HTTPException(400, "Video file required")

    temp = tempfile.NamedTemporaryFile(delete=False)
    temp.write(await file.read())

    cap = cv2.VideoCapture(temp.name)

    frames = []
    reps = 0
    down = False
    good_frames = 0
    total_frames = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = pose.process(rgb)

        if result.pose_landmarks:
            lms = result.pose_landmarks.landmark

            hip = lm(lms, mp_pose.PoseLandmark.RIGHT_HIP)
            knee = lm(lms, mp_pose.PoseLandmark.RIGHT_KNEE)
            ankle = lm(lms, mp_pose.PoseLandmark.RIGHT_ANKLE)

            shoulder = lm(lms, mp_pose.PoseLandmark.RIGHT_SHOULDER)
            elbow = lm(lms, mp_pose.PoseLandmark.RIGHT_ELBOW)
            wrist = lm(lms, mp_pose.PoseLandmark.RIGHT_WRIST)

            knee_angle = angle(hip, knee, ankle)
            elbow_angle = angle(shoulder, elbow, wrist)

            # Rep counting
            if knee_angle < 90:
                down = True
            if knee_angle > 160 and down:
                reps += 1
                down = False

            good_form = elbow_angle > 140
            if good_form:
                good_frames += 1

            total_frames += 1

            frames.append({
                "knee_angle": round(knee_angle, 1),
                "elbow_angle": round(elbow_angle, 1),
                "good_form": good_form
            })

    cap.release()

    score = int((good_frames / max(total_frames, 1)) * 100)

    feedback = []
    if score < 60:
        feedback.append("Focus on arm extension and balance.")
    if reps == 0:
        feedback.append("No clear reps detected — make sure your full body is visible.")
    if score >= 80:
        feedback.append("Great consistency and form!")

    return {
        "reps": reps,
        "overall_score": score,
        "coach_feedback": feedback,
        "frames": frames
    }

@app.get("/")
def health():
    return {"status": "LevelUp backend running"}


