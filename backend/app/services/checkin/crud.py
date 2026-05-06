from datetime import date
from typing import Optional
from sqlalchemy.orm import Session
from app.db import models
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy import func, inspect
from app.common.connect import get_or_create_connect_group
from app.common.first_timer import has_first_timer_event_for_member_today, has_first_timer_event_for_member_today_any_service
from app.common.service import _event_name_for_service


def mark_attendance_for_service(db: Session, member_id, service_type: str, connect_name: str | None = None):
    today = date.today()
    normalized_connect = (connect_name or "").strip()
    service = get_or_create_service(
        db,
        service_type=service_type,
        connect_name=normalized_connect if service_type == "connect" else None,
    )
    if service_type == "connect":
        existing_connect = (
            db.query(models.Attendance)
            .filter(
                models.Attendance.member_id == member_id,
                models.Attendance.service_date == today,
                models.Attendance.service_type == "connect",
            )
            .first()
        )
        if existing_connect:
            return False

    att = models.Attendance(
        member_id=member_id,
        service_id=service.id,
        service_type=service_type,
        connect_name=normalized_connect,
        service_date=today,
    )
    db.add(att)
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False


def get_or_create_service(
    db: Session,
    service_type: str,
    connect_name: Optional[str] = None
):
    normalized_service = service_type.strip().lower()
    row = (
        db.query(models.Service)
        .filter(func.lower(models.Service.name) == normalized_service)
        .first()
    )
    if row:
        if service_type == "connect" and connect_name:
            get_or_create_connect_group(db, connect_name, service_id=row.id)
        return row

    row = models.Service(
        name=service_type.strip(),
        theme=None,
        location=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    if service_type == "connect" and connect_name:
        get_or_create_connect_group(db, connect_name, service_id=row.id)
    return row

def mark_first_timer_event(
    db: Session,
    member_id,
    service_type: str,
    connect_name: Optional[str] = None
):
    today = date.today()
    normalized_service = service_type.strip().lower()
    service_name = _event_name_for_service(normalized_service, connect_name)
    if has_first_timer_event_for_member_today(db, member_id, service_type, connect_name):
        return True

    service = get_or_create_service(
        db,
        service_type=normalized_service,
        connect_name=connect_name if normalized_service == "connect" else None,
    )
    row = models.FirstTimerEvent(
        member_id=member_id,
        service_id=service.id,
        service_type=normalized_service,
        service_name=service_name,
        service_date=today,
    )
    db.add(row)
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return (
            has_first_timer_event_for_member_today(db, member_id, service_type, connect_name)
            or has_first_timer_event_for_member_today_any_service(db, member_id)
        )

def get_attendance_for_member_service_today(db: Session, member_id, service_type: str):
    # Some environments may not have run all migrations yet.
    # Avoid hard failures when attendance table is missing.
    if not inspect(db.bind).has_table("attendance"):
        return None

    today = date.today()
    try:
        return (
            db.query(models.Attendance)
            .filter(
                models.Attendance.member_id == member_id,
                models.Attendance.service_date == today,
                models.Attendance.service_type == service_type,
            )
            .first()
        )
    except ProgrammingError:
        db.rollback()
        return None




