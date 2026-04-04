import os
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.db.database import get_db
from app.models.user import User
from app.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    sport: Optional[str] = None


@router.post("/")
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        from openai import OpenAI
        import httpx

        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            http_client=httpx.Client(),
        )

        # Get user's recent performance for context
        context = _get_user_context(user, db, request.sport)

        system_prompt = f"""You are LevelUp AI, an expert sports performance coach assistant built into the LevelUp app.

You specialize in:
- Sports technique and form correction
- Training strategies and periodization
- Sport-specific drills and exercises
- Mental performance and confidence
- Injury prevention and recovery
- Nutrition for athletes
- Game strategy and tactics

{context}

Guidelines:
- Give specific, actionable advice
- Reference the athlete's actual performance data when relevant
- Be encouraging but honest
- Keep responses concise — 2-4 short paragraphs max
- Use bullet points for lists of tips or drills
- Always relate advice back to improving their score or fixing their form issues
- If asked about something outside sports/fitness, politely redirect to sports topics"""

        messages = [{"role": "system", "content": system_prompt}]
        for msg in request.messages:
            messages.append({"role": msg.role, "content": msg.content})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=400,
            temperature=0.8,
        )

        reply = response.choices[0].message.content.strip()

        return {"reply": reply, "role": "assistant"}

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Chat failed. Please try again.")


def _get_user_context(user: User, db: Session, sport: Optional[str]) -> str:
    """Gets user's performance context to personalize chat."""
    try:
        from app.models.performance_log import PerformanceLog

        logs = (
            db.query(PerformanceLog)
            .filter(PerformanceLog.user_id == user.id)
            .order_by(PerformanceLog.created_at.desc())
            .limit(5)
            .all()
        )

        if not logs:
            return f"This athlete is new to LevelUp. Their preferred sport is {sport or 'not set yet'}."

        recent = logs[0]
        scores = [l.score for l in logs if l.score]
        avg_score = sum(scores) / len(scores) if scores else 0

        recent_issues = []
        if recent.metrics and isinstance(recent.metrics, dict):
            recent_issues = recent.metrics.get("form_issues", [])

        sports = list(set(l.sport for l in logs if l.sport))

        context = f"""Athlete context:
- Username: {user.username}
- Sports they train: {', '.join(sports)}
- Total sessions: {len(logs)}
- Average score: {avg_score:.0f}/100
- Most recent score: {recent.score}/100 in {recent.sport}
- Recent form issues: {', '.join(recent_issues) if recent_issues else 'None detected'}
- Current focus sport: {sport or recent.sport}"""

        return context

    except Exception as e:
        logger.warning(f"Could not get user context: {e}")
        return f"Athlete is using LevelUp to improve their {sport or 'sports'} performance."