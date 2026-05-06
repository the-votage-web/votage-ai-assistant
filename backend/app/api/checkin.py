from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.checkin.check_in import handle_checkin

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class CheckinIn(BaseModel):
    session_id: str
    message: str

class CheckinOut(BaseModel):
    reply: str

@router.post("/checkin", response_model=CheckinOut)
def checkin(payload: CheckinIn, db: Session = Depends(get_db)):
    reply = handle_checkin(db, payload.session_id, payload.message)
    return CheckinOut(reply=reply)
