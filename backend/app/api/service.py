from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.constants.service import ServiceCreateIn, ServiceOut
from app.services.service.service import find_service_by_name, create_service


router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/services", response_model=ServiceOut)
def create_service(payload: ServiceCreateIn, db: Session = Depends(get_db)):
    existing = find_service_by_name(db=db, name=payload.name)
    if existing:
        raise HTTPException(status_code=409, detail="Service already exists.")

    row = create_service(
        db=db,
        name=payload.name,
        theme=payload.theme,
        location=payload.location,
    )

    return ServiceOut(
        id=row.id,
        name=row.name,
        theme=row.theme,
        location=row.location,
    )
