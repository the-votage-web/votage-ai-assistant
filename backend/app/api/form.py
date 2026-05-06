from app.constants.register import RegisterOptionsOut
from app.services.register.register import handle_service_options, handle_registration
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.constants.register import RegistrationIn, RegistrationOut

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/register/options", response_model=RegisterOptionsOut)
def get_register_options(db: Session = Depends(get_db)):
    return handle_service_options(db)

@router.post("/register", response_model=RegistrationOut)
def create_registration(payload: RegistrationIn, db: Session = Depends(get_db)):
    return handle_registration(payload, db)