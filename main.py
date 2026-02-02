# main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
import uuid
from pathlib import Path
from datetime import datetime
import cv2
import mediapipe as mp
import numpy as np

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

# Initialize MediaPipe Pose
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=2,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

def analyze_basketball_shot(video_path: str):
    """Analyze basketball shooting form using pose detection"""
    cap = cv2.VideoCapture(video_path)
    
    # Data collection
    angles = []
    velocities = []
    balance_scores = []
    frame_count = 0
    
    prev_wrist_y = None
    shooting_detected = False
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb_frame)
        
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            
            # Get key points
            right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
            right_elbow = landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW]
            right_wrist = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST]
            right_hip = landmarks[mp_pose.PoseLandmark.RIGHT_HIP]
            right_knee = landmarks[mp_pose.PoseLandmark.RIGHT_KNEE]
            right_ankle = landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE]
            
            # Calculate elbow angle
            elbow_angle = calculate_angle(
                [right_shoulder.x, right_shoulder.y],
                [right_elbow.x, right_elbow.y],
                [right_wrist.x, right_wrist.y]
            )
            angles.append(elbow_angle)
            
            # Calculate balance (hip-knee-ankle alignment)
            balance_score = calculate_balance(
                [right_hip.x, right_hip.y],
                [right_knee.x, right_knee.y],
                [right_ankle.x, right_ankle.y]
            )
            balance_scores.append(balance_score)
            
            # Detect shooting motion (wrist movement)
            if prev_wrist_y is not None:
                velocity = abs(right_wrist.y - prev_wrist_y)
                velocities.append(velocity)
                if velocity > 0.05:  # Threshold for shot detection
                    shooting_detected = True
            
            prev_wrist_y = right_wrist.y
    
    cap.release()
    
    # Analyze collected data
    analysis = generate_feedback(angles, balance_scores, velocities, shooting_detected)
    return analysis

def calculate_angle(point1, point2, point3):
    """Calculate angle between three points"""
    a = np.array(point1)
    b = np.array(point2)
    c = np.array(point3)
    
    ba = a - b
    bc = c - b
    
    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
    angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))
    
    return np.degrees(angle)

def calculate_balance(hip, knee, ankle):
    """Calculate balance score based on body alignment"""
    # Check vertical alignment of hip-knee-ankle
    hip_knee_angle = abs(hip[0] - knee[0])
    knee_ankle_angle = abs(knee[0] - ankle[0])
    
    # Lower deviation = better balance
    deviation = hip_knee_angle + knee_ankle_angle
    balance_score = max(0, 100 - (deviation * 1000))
    
    return balance_score

def generate_feedback(angles, balance_scores, velocities, shooting_detected):
    """Generate coaching feedback based on analysis"""
    avg_angle = np.mean(angles) if angles else 0
    avg_balance = np.mean(balance_scores) if balance_scores else 0
    max_velocity = max(velocities) if velocities else 0
    
    positives = []
    focus_areas = []
    training_plan = []
    
    # Analyze elbow angle (ideal: 90-110 degrees at release)
    if 85 <= avg_angle <= 115:
        positives.append("Excellent elbow angle throughout the shot")
    else:
        focus_areas.append(f"Elbow angle averaging {avg_angle:.1f}° - aim for 90-110°")
        training_plan.append("Wall shooting drill: Focus on L-shape arm position")
    
    # Analyze balance
    if avg_balance > 70:
        positives.append("Strong balance and body control")
    else:
        focus_areas.append("Balance needs improvement - body swaying detected")
        training_plan.append("Single-leg balance drills: 3 sets of 30 seconds each")
        training_plan.append("Box jumps for stability: 3 sets of 10 reps")
    
    # Analyze shot motion
    if shooting_detected:
        if max_velocity > 0.1:
            positives.append("Good shooting motion detected with proper follow-through")
        else:
            focus_areas.append("Shot motion appears too slow or mechanical")
            training_plan.append("Practice shooting with full extension and follow-through")
    else:
        focus_areas.append("No clear shooting motion detected in video")
    
    # Calculate overall score
    overall_score = int((avg_balance * 0.4) + 
                       (min(abs(100 - avg_angle), 50) * 0.4) + 
                       (max_velocity * 100 * 0.2))
    
    return {
        "sport": "basketball",
        "overall_score": min(overall_score, 100),
        "positives": positives if positives else ["Keep practicing! Improvement takes time"],
        "focus_areas": focus_areas if focus_areas else ["Continue working on fundamentals"],
        "training_plan": training_plan if training_plan else ["Form shooting: 50 reps daily"],
        "metrics": {
            "average_elbow_angle": round(avg_angle, 1),
            "average_balance_score": round(avg_balance, 1),
            "shot_detected": shooting_detected,
            "frames_analyzed": len(angles)
        },
        "analyzed_at": datetime.now().isoformat()
    }

def generate_safe_filename(original_filename: str) -> str:
    file_ext = Path(original_filename).suffix
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    return f"{timestamp}_{unique_id}{file_ext}"

@app.get("/")
def root():
    return {
        "status": "Sports Coach AI running",
        "version": "1.0.0",
        "supported_sports": ["basketball"],
        "endpoints": {
            "upload": "/upload-video",
            "health": "/health"
        }
    }

@app.post("/upload-video")
async def upload_video(file: UploadFile = File(...)):
    try:
        # Validate file type
        if not file.content_type.startswith('video/'):
            raise HTTPException(400, "Only video files allowed")
        
        # Check file size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(400, f"File too large. Max: {MAX_FILE_SIZE // (1024*1024)}MB")
        
        # Save file
        safe_filename = generate_safe_filename(file.filename)
        file_path = os.path.join(UPLOAD_DIR, safe_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # AI ANALYSIS
        analysis = analyze_basketball_shot(file_path)
        
        return {
            "success": True,
            "message": "Video analyzed successfully",
            "filename": safe_filename,
            "file_size": file_size,
            "analysis": analysis
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Analysis error: {str(e)}")
    finally:
        await file.close()

@app.get("/health")
def health():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    }
```

### 3. **Requirements** (requirements.txt)
```
fastapi==0.104.1
uvicorn==0.24.0
python-multipart==0.0.6
opencv-python==4.8.1.78
mediapipe==0.10.8
numpy==1.24.3
