from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os

app = FastAPI()

# Allow VibeCode / frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # later you can restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/")
def health_check():
    return {"status": "Level Up backend running"}

@app.post("/analyze")
async def analyze_video(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    # Save uploaded video
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 🔥 PLACEHOLDER AI LOGIC (we’ll replace this later)
    analysis_result = {
        "filename": file.filename,
        "strengths": [
            "Good posture",
            "Consistent movement"
        ],
        "improvements": [
            "Footwork timing",
            "Reaction speed"
        ],
        "summary": "Overall strong fundamentals with room to improve speed and balance."
    }

    return analysis_result
python -m uvicorn main:app --reload
