from app.constants.register import RegistrationIn
from app.constants.register import RegisterOptionsOut
from app.constants.connect import CONNECT_GROUPS
from app.constants.service import DEFAULT_SERVICE_TYPES
from app.common.connect import get_connect_group_names
from sqlalchemy.orm import Session
from app.common.service import get_service_types
from app.services.register.crud import register_member_with_attendance_transaction
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, ProgrammingError
from app.constants.register import RegistrationOut


def handle_service_options(db: Session):
    service_types = get_service_types(db)
    connect_groups = get_connect_group_names(db)

    # Keep register validator-compatible types if DB has custom service names.
    allowed = set(DEFAULT_SERVICE_TYPES)
    service_types = [s for s in service_types if s in allowed] or DEFAULT_SERVICE_TYPES
    connect_groups = connect_groups or CONNECT_GROUPS

    return RegisterOptionsOut(service_types=service_types, connect_groups=connect_groups)

def handle_registration(payload: RegistrationIn, db: Session):
    try:
        register_member_with_attendance_transaction(
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
        print("error is", err)
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
        import traceback
        print(f"Database Schema Error: {str(exc)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Database schema error: {str(exc.orig)}",
        ) from exc
    except Exception as exc:
        import traceback
        print(f"Registration Exception: {str(exc)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Registration failed: {str(exc)}",
        ) from exc

    return RegistrationOut(ok=True, message="Registration completed successfully.")
      