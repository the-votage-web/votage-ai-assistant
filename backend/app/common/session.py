import re
from app.db import models
from sqlalchemy.orm import Session
from app.constants.faq import FAQ_SESSION_START_TOKENS, FAQ_SESSION_END_TOKENS

def get_or_create_session(db: Session, session_id: str) -> models.ChatSession:
    s = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not s:
        s = models.ChatSession(id=session_id, state_json="{}")
        db.add(s)
        db.commit()
    return s

def _is_end_session_message(message: str) -> bool:
    normalized = re.sub(r"\s+", " ", message.lower()).strip()
    return normalized in {"end", "stop", "cancel", "quit", "end session", "stop session", "cancel session"}

def _is_faq_session_start_message(message: str) -> bool:
    normalized = re.sub(r"\s+", " ", message.lower()).strip()
    return normalized in FAQ_SESSION_START_TOKENS

def _is_faq_session_end_message(message: str) -> bool:
    normalized = re.sub(r"\s+", " ", message.lower()).strip()
    return normalized in FAQ_SESSION_END_TOKENS
