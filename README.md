# level-up-backend
Backend API and AI video analysis for the Level Up youth sports training app
## Deploy on Render

- **Python version**: This app uses MediaPipe, which does not support Python 3.13. Render will use the version from the **`.python-version`** file in the repo root (set to `3.10`). Alternatively, in Render Dashboard → Environment, set **`PYTHON_VERSION`** = `3.10.14`.
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Local run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

API docs: http://127.0.0.1:8000/docs
