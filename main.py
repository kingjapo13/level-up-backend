from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def health_check():
    return {"status": "Level Up backend running"}
from fastapi import UploadFile, File

@app.post("/analyze")
async def analyze_video(file: UploadFile = File(...)):
    # TODO: save video temporarily
    # TODO: run AI video analysis
    # TODO: return results

    return {
        "filename": file.filename,
        "strengths": ["Good balance", "Consistent motion"],
        "improvements": ["Footwork timing"]
    }
