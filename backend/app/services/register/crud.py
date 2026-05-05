from sqlalchemy import inspect, func
from sqlalchemy.orm import Session
from datetime import date, datetime, timezone
from app.db import models
from typing import Optional
from app.common.utils import find_member_by_phone
from app.common.service import _event_name_for_service


def register_member_with_attendance_transaction(
    db: Session,
    phone_number: str,
    first_name: str,
    last_name: str,
    email: str,
    gender: str,
    marital_status: str,
    service_type: str,
    connect_name: Optional[str] = None
):
    db_inspector = inspect(db.bind)
    required_tables = ["members", "service", "connect_group", "attendance", "first_timer_events"]
    for table_name in required_tables:
        if not db_inspector.has_table(table_name):
            raise ValueError(f"missing_table:{table_name}")
            
    if find_member_by_phone(db, phone_number):
        raise ValueError("phone_exists")

    normalized_service = service_type.strip().lower()
    normalized_connect = (connect_name or "").strip() or None
    today = date.today()

    try:
        service = (
            db.query(models.Service)
            .filter(func.lower(models.Service.name) == normalized_service)
            .first()
        )
        if not service:
            service = models.Service(
                name=service_type.strip(),
                theme=None,
                location=None,
            )
            db.add(service)
            db.flush()

        if normalized_service == "connect" and normalized_connect:
            group = (
                db.query(models.ConnectGroup)
                .filter(func.lower(models.ConnectGroup.name) == normalized_connect.lower())
                .first()
            )
            if group:
                if group.service_id != service.id:
                    group.service_id = service.id
            else:
                group = models.ConnectGroup(
                    service_id=service.id,
                    name=normalized_connect,
                    description="Auto-created from registration",
                    meeting_time="TBD",
                    meeting_day="TBD",
                )
                db.add(group)
                db.flush()

        member = models.Member(
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            email=email,
            gender=gender,
            marital_status=marital_status,
            first_timer=True,
            connect_name=normalized_connect,
            date_joined=datetime.now(timezone.utc),
        )
        db.add(member)
        db.flush()

        attendance = models.Attendance(
            member_id=member.id,
            service_id=service.id,
            service_type=normalized_service,
            connect_name=normalized_connect or "",
            service_date=today,
        )
        db.add(attendance)
        db.flush()

        event = models.FirstTimerEvent(
            member_id=member.id,
            service_id=service.id,
            service_type=normalized_service,
            service_name=_event_name_for_service(normalized_service, normalized_connect),
            service_date=today,
        )
        db.add(event)
        db.flush()

        db.commit()
        db.refresh(member)
        return member
    except Exception as e:
        import traceback
        print(f"Transaction Error in register_member_with_attendance_transaction: {str(e)}")
        traceback.print_exc()
        db.rollback()
        raise e

