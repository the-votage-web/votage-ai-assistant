from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.ai.agent import handle_message, debug_faq_match

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
    reply = handle_message(db, payload.session_id, payload.message)
    return ChatOut(reply=reply)


@router.post("/debug/faq-match")
def faq_match_debug(payload: FaqDebugIn):
    return debug_faq_match(payload.question)
