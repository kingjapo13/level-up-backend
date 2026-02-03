# Level Up Backend

Backend API and AI video analysis for the Level Up youth sports training app.

## Deploy on Render

This app uses **MediaPipe**, which does **not** support Python 3.13. Render defaults to 3.13, so you must set Python 3.10:

### Option A: Set in Render Dashboard (do this if deploy still uses 3.13)

1. Open [Render Dashboard](https://dashboard.render.com) → your **level-up-backend** (or Web Service) → **Environment**.
2. Click **Add Environment Variable**.
3. **Key:** `PYTHON_VERSION`  
   **Value:** `3.10.14`
4. **Save Changes**, then trigger a **Manual Deploy** (or push a new commit).

Render will then use Python 3.10 for the next build and MediaPipe will work.

### Option B: New service from Blueprint

If you create a new Web Service from this repo using **Blueprint** and a `render.yaml`, the repo’s `render.yaml` already sets `PYTHON_VERSION=3.10.14`.

- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Local run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

API docs: http://127.0.0.1:8000/docs
