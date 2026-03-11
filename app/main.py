import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import engine
import app.db.models
from app.db.database import Base
from app.routers import auth, analyze, athletes, dashboard, notifications, performance_logs, webhooks
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


@app.get("/")
def root():
    return {"service": "LevelUp AI Coaching API", "status": "running", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}