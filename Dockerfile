# Dockerfile for Level Up backend + video processing (CPU)
# Note: mediapipe pip package requires manylinux wheels; this image uses Debian slim.
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system deps (ffmpeg, build tools for some wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    git \
    curl \
    libglib2.0-0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy project files
WORKDIR /app
COPY . /app

# Upgrade pip
RUN pip install --upgrade pip setuptools wheel

# Install Python dependencies
# If you use a large torch wheel for GPU, change this line to the appropriate wheel
# For CPU-only, pip install torch may work; if you need a specific torch version check official instructions.
RUN pip install -r requirements.txt

# Expose the FastAPI port
EXPOSE 8000

# Default command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
