"""Chat logging: record every FAQ question/answer so the team can review how the
bot is doing and which questions it could not answer (the gaps to fill)."""
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.db.models import ChatLog


def log_chat(db: Session, session_id: str, question: str, answer: str,
             answered: bool, top_score: Optional[float]) -> None:
    """Insert one chat log row. Never raises — logging must not break a reply."""
    try:
        db.add(ChatLog(
            session_id=session_id,
            question=question,
            answer=answer,
            answered=answered,
            top_score=top_score,
        ))
        db.commit()
    except Exception as exc:
        db.rollback()
        print(f"chat log insert failed: {exc!r}")


def get_logs(db: Session, status: str = "all", q: Optional[str] = None, limit: int = 100):
    """Return recent chat logs (newest first) as plain dicts.

    status: "all" | "answered" | "unanswered". q: optional keyword (case-insensitive)
    matched against the question text.
    """
    query = db.query(ChatLog)
    if status == "unanswered":
        query = query.filter(ChatLog.answered.is_(False))
    elif status == "answered":
        query = query.filter(ChatLog.answered.is_(True))
    if q:
        query = query.filter(ChatLog.question.ilike(f"%{q}%"))
    rows = query.order_by(ChatLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": str(r.id),
            "session_id": r.session_id,
            "question": r.question,
            "answer": r.answer,
            "answered": r.answered,
            "top_score": r.top_score,
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def mark_resolved(db: Session, log_id: str) -> None:
    """Stamp a chat log as resolved (an admin answered this gap). Never raises."""
    try:
        row = db.query(ChatLog).filter(ChatLog.id == log_id).first()
        if row:
            row.resolved_at = datetime.now(timezone.utc)
            db.commit()
    except Exception as exc:
        db.rollback()
        print(f"mark_resolved failed: {exc!r}")
