"""Chat logging: record every FAQ question/answer so the team can review how the
bot is doing and which questions it could not answer (the gaps to fill)."""
from typing import Optional
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


def get_logs(db: Session, unanswered_only: bool = False, limit: int = 100):
    """Return recent chat logs (newest first) as plain dicts."""
    query = db.query(ChatLog)
    if unanswered_only:
        query = query.filter(ChatLog.answered.is_(False))
    rows = query.order_by(ChatLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": str(r.id),
            "session_id": r.session_id,
            "question": r.question,
            "answer": r.answer,
            "answered": r.answered,
            "top_score": r.top_score,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
