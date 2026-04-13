import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db.database import engine, Base
import app.db.models
from app.routers import (
    auth, analyze, athletes, dashboard,
    notifications, performance_logs,
    webhooks, chat, comparison, leaderboard, recruiting
)
from services.scheduler import start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_URL = os.getenv("FRONTEND_URL", "*")


def run_migrations():
    """Run all database column migrations safely."""
    migrations = [
        # Users table
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS age INTEGER",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS location VARCHAR",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS device_token VARCHAR",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS personality_mode VARCHAR DEFAULT 'supportive'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR DEFAULT 'athlete'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS invite_code VARCHAR",

        # Performance logs table
        "ALTER TABLE performance_logs ADD COLUMN IF NOT EXISTS athlete_id INTEGER",
        "ALTER TABLE performance_logs ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()",

        # Athletes table
        "ALTER TABLE athletes ADD COLUMN IF NOT EXISTS age INTEGER",
        "ALTER TABLE athletes ADD COLUMN IF NOT EXISTS location VARCHAR",
        "ALTER TABLE athletes ADD COLUMN IF NOT EXISTS bio VARCHAR",
        "ALTER TABLE athletes ADD COLUMN IF NOT EXISTS looking_for VARCHAR",
        "ALTER TABLE athletes ADD COLUMN IF NOT EXISTS skill_level VARCHAR",
        "ALTER TABLE athletes ADD COLUMN IF NOT EXISTS best_score FLOAT",
        "ALTER TABLE athletes ADD COLUMN IF NOT EXISTS total_sessions INTEGER DEFAULT 0",
        "ALTER TABLE athletes ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",

        # Athlete profiles table
        "ALTER TABLE athlete_profiles ADD COLUMN IF NOT EXISTS display_name VARCHAR",
        "ALTER TABLE athlete_profiles ADD COLUMN IF NOT EXISTS secondary_sports VARCHAR",
        "ALTER TABLE athlete_profiles ADD COLUMN IF NOT EXISTS avg_score FLOAT",
        "ALTER TABLE athlete_profiles ADD COLUMN IF NOT EXISTS best_score FLOAT",
        "ALTER TABLE athlete_profiles ADD COLUMN IF NOT EXISTS total_sessions INTEGER DEFAULT 0",
        "ALTER TABLE athlete_profiles ADD COLUMN IF NOT EXISTS bio VARCHAR",
        "ALTER TABLE athlete_profiles ADD COLUMN IF NOT EXISTS looking_for VARCHAR",
        "ALTER TABLE athlete_profiles ADD COLUMN IF NOT EXISTS is_visible BOOLEAN DEFAULT TRUE",
        "ALTER TABLE athlete_profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",
    ]

    try:
        with engine.connect() as conn:
            for sql in migrations:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                    logger.info(f"Migration OK: {sql[:70]}")
                except Exception as e:
                    logger.warning(f"Migration skipped ({sql[:40]}): {str(e)[:60]}")
        logger.info("All migrations complete.")
    except Exception as e:
        logger.error(f"Migration block failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified.")
    run_migrations()
    scheduler = start_scheduler()
    logger.info("Scheduler started.")
    yield
    scheduler.shutdown()
    logger.info("Scheduler stopped.")


app = FastAPI(
    title="LevelUp AI Coaching API",
    version="1.0.0",
    description="AI-powered sports coaching.",
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
app.include_router(recruiting.router)


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