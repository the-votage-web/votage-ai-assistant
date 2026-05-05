from app.services.service.service import find_service_by_id
from app.services.connect.connect import find_connect_group_by_name, create_connect_group
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app.db.session import SessionLocal
from app.constants.connect import ConnectGroupCreateIn, ConnectGroupOut


router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/connect-groups", response_model=ConnectGroupOut)
def create_connect_group(payload: ConnectGroupCreateIn, db: Session = Depends(get_db)):
    existing = find_connect_group_by_name(db=db, name=payload.name)
    if existing:
        raise HTTPException(status_code=409, detail="Connect group already exists.")

    service = find_service_by_id(db=db, service_id=payload.service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found for service_id.")

    row = create_connect_group(
        db=db,
        name=payload.name,
        description=payload.description,
        meeting_time=payload.meeting_time,
        meeting_day=payload.meeting_day,
        service_id=payload.service_id,
    )
    return ConnectGroupOut(
        id=row.id,
        service_id=row.service_id,
        name=row.name,
        description=row.description,
        meeting_time=row.meeting_time,
        meeting_day=row.meeting_day,
    )