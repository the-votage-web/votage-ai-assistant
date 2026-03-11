from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.api.schemas.form import (
    ConnectGroupCreateIn,
    ConnectGroupOut,
    DEFAULT_CONNECT_GROUPS,
    DEFAULT_SERVICE_TYPES,
    RegisterOptionsOut,
    RegistrationIn,
    RegistrationOut,
    ServiceCreateIn,
    ServiceOut,
)
from app.db import crud
from app.db.session import SessionLocal

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/register/options", response_model=RegisterOptionsOut)
def get_register_options(db: Session = Depends(get_db)):
    service_types = crud.get_service_types(db)
    connect_groups = crud.get_connect_group_names(db)

    # Keep register validator-compatible types if DB has custom service names.
    allowed = set(DEFAULT_SERVICE_TYPES)
    service_types = [s for s in service_types if s in allowed] or DEFAULT_SERVICE_TYPES
    connect_groups = connect_groups or DEFAULT_CONNECT_GROUPS

    return RegisterOptionsOut(service_types=service_types, connect_groups=connect_groups)


@router.post("/connect-groups", response_model=ConnectGroupOut)
def create_connect_group(payload: ConnectGroupCreateIn, db: Session = Depends(get_db)):
    existing = crud.find_connect_group_by_name(db=db, name=payload.name)
    if existing:
        raise HTTPException(status_code=409, detail="Connect group already exists.")

    service = crud.find_service_by_id(db=db, service_id=payload.service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found for service_id.")

    row = crud.create_connect_group(
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


@router.post("/services", response_model=ServiceOut)
def create_service(payload: ServiceCreateIn, db: Session = Depends(get_db)):
    existing = crud.find_service_by_name(db=db, name=payload.name)
    if existing:
        raise HTTPException(status_code=409, detail="Service already exists.")

    row = crud.create_service(
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


@router.post("/register", response_model=RegistrationOut)
def create_registration(payload: RegistrationIn, db: Session = Depends(get_db)):
    try:
        crud.register_member_with_attendance_transaction(
            db=db,
            phone_number=payload.phone_number,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            gender=payload.gender,
            marital_status=payload.marital_status,
            service_type=payload.service_type,
            connect_name=payload.connect_name,
        )
    except ValueError as exc:
        err = str(exc)
        if err == "phone_exists":
            raise HTTPException(
                status_code=409,
                detail="This phone number is already registered.",
            ) from exc
        if err.startswith("missing_table:"):
            table = err.split(":", 1)[1]
            raise HTTPException(
                status_code=500,
                detail=f"Database table '{table}' is missing. Run migrations and try again.",
            ) from exc
        raise HTTPException(
            status_code=400,
            detail="Invalid registration payload.",
        ) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Registration conflict: {str(exc.orig)}",
        ) from exc
    except ProgrammingError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database schema error: {str(exc.orig)}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Registration failed: {exc.__class__.__name__}",
        ) from exc

    return RegistrationOut(ok=True, message="Registration completed successfully.")
