from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.faq.faq import handle_faq, FAQTemporarilyUnavailableError

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
