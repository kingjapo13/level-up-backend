from fastapi import FastAPI, UploadFile, File
from mediapipe import solutions
import cv2
import numpy as np
import tempfile

app = FastAPI()

mp_pose = solutions.pose
pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# ---------- Math ----------

def angle(a, b, c):
    a, b, c = map(np.array, (a, b, c))
    rad = np.arctan2(c[1]-b[1], c[0]-b[0]) - \
          np.arctan2(a[1]-b[1], a[0]-b[0])
    deg = abs(rad * 180 / np.pi)
    return 360 - deg if deg > 180 else deg

def lm(lms, idx):
    p = lms[idx]
    return [p.x, p.y]

# ---------- AI Logic ----------

def detect_rep(knee_angle, state):
    if knee_angle < 90:
        state["down"] = True
    if knee_angle > 160 and state["down"]:
        state["count"] += 1
        state["down"] = False

def basketball_form(elbow, shoulder, wrist):
    elbow_angle = angle(shoulder, elbow, wrist)
    return elbow_angle > 140

def golf_phase(hip, shoulder, wrist):
    if wrist[1] < shoulder[1]:
        return "backswing"
    if wrist[1] > hip[1]:
        return "downswing"
    return "setup"

def score(form_flags):
    good = sum(form_flags)
    return int((good / max(len(form_flags),1)) * 100)

# ---------- API ----------

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.write(await file.read())

    cap = cv2.VideoCapture(tmp.name)

    frames = []
    rep_state = {"count": 0, "down": False}
    form_checks = []

    frame_id = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        res = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if res.pose_landmarks:
            lms = res.pose_landmarks.landmark

            hip = lm(lms, mp_pose.PoseLandmark.RIGHT_HIP)
            knee = lm(lms, mp_pose.PoseLandmark.RIGHT_KNEE)
            ankle = lm(lms, mp_pose.PoseLandmark.RIGHT_ANKLE)

            shoulder = lm(lms, mp_pose.PoseLandmark.RIGHT_SHOULDER)
            elbow = lm(lms, mp_pose.PoseLandmark.RIGHT_ELBOW)
            wrist = lm(lms, mp_pose.PoseLandmark.RIGHT_WRIST)

            knee_angle = angle(hip, knee, ankle)
            detect_rep(knee_angle, rep_state)

            good_shot = basketball_form(elbow, shoulder, wrist)
            phase = golf_phase(hip, shoulder, wrist)

            form_checks.append(good_shot)

            frames.append({
                "frame": frame_id,
                "knee_angle": round(knee_angle,2),
                "basketball_form_good": good_shot,
                "golf_phase": phase
            })

        frame_id += 1

    cap.release()

    overall_score = score(form_checks)

    feedback = []
    if overall_score < 60:
        feedback.append("Work on joint alignment and consistency.")
    if rep_state["count"] < 5:
        feedback.append("Increase depth and full extension.")
    if overall_score >= 80:
        feedback.append("Excellent form consistency!")

    return {
        "frames": frames,
        "reps": rep_state["count"],
        "score": overall_score,
        "coach_feedback": feedback
    }

@app.get("/")
def health():
    return {"status": "AI coach running"}

