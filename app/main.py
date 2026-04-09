import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import engine, Base
import app.db.models
from app.routers import (
    auth, analyze, athletes, dashboard,
    notifications, performance_logs,
    webhooks, chat, comparison, leaderboard
)
from services.scheduler import start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_URL = os.getenv("FRONTEND_URL", "*")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified.")

    # Run column migrations for new columns
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            migrations = [
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS age INTEGER",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS location VARCHAR",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS device_token VARCHAR",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS personality_mode VARCHAR DEFAULT 'supportive'",
            ]
            for sql in migrations:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                    logger.info(f"Migration OK: {sql[:50]}")
                except Exception as e:
                    logger.warning(f"Migration skipped: {e}")
    except Exception as e:
        logger.warning(f"Migration block failed: {e}")

    scheduler = start_scheduler()
    yield
    scheduler.shutdown()
    logger.info("Scheduler stopped.")

app = FastAPI(
    title="LevelUp AI Coaching API",
    version="1.0.0",
    description="AI-powered sports coaching — analyze video, get feedback, track progress.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if FRONTEND_URL == "*" else [FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(analyze.router)
app.include_router(athletes.router)
app.include_router(dashboard.router)
app.include_router(notifications.router)
app.include_router(performance_logs.router)
app.include_router(webhooks.router)
app.include_router(chat.router)
app.include_router(comparison.router)
app.include_router(leaderboard.router)

@app.get("/")
def root():
    return {
        "service": "LevelUp AI Coaching API",
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}