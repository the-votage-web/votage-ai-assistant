from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.config import settings
from app.services.faq.faq import handle_faq, FAQTemporarilyUnavailableError
from app.services.faq.logs import get_logs

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ChatIn(BaseModel):
    session_id: str
    message: str

class ChatOut(BaseModel):
    reply: str

class FaqDebugIn(BaseModel):
    question: str

@router.post("/chat", response_model=ChatOut)
def chat(payload: ChatIn, db: Session = Depends(get_db)):
    try:
        reply = handle_faq(db, payload.session_id, payload.message)
    except FAQTemporarilyUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ChatOut(reply=reply)


def require_admin(x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    """Gate admin-only endpoints. Deny by default when ADMIN_API_KEY is not set."""
    expected = settings.ADMIN_API_KEY
    if not expected or x_admin_key != expected:
        raise HTTPException(status_code=403, detail="Admin access required.")


@router.get("/faq/logs")
def faq_logs(
    unanswered: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_admin),
):
    """View recent chat logs (admin only). ?unanswered=true shows only the gaps the bot couldn't answer."""
    limit = max(1, min(limit, 500))
    return get_logs(db, unanswered_only=unanswered, limit=limit)
