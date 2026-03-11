from datetime import date, datetime, timezone
from typing import List
from uuid import UUID
from sqlalchemy import func, inspect
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, ProgrammingError
from app.db import models


def get_or_create_session(db: Session, session_id: str) -> models.ChatSession:
    s = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not s:
        s = models.ChatSession(id=session_id, state_json="{}")
        db.add(s)
        db.commit()
    return s


def find_member_by_phone(db: Session, phone: str):
    return db.query(models.Member).filter(models.Member.phone_number == phone).first()


def _split_full_name(full_name: str) -> tuple[str, str]:
    parts = [p for p in full_name.strip().split() if p]
    if not parts:
        return "Member", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def create_member(db: Session, full_name: str, phone: str, aliases: str = ""):
    first_name, last_name = _split_full_name(full_name)
    m = models.Member(
        first_name=first_name,
        last_name=last_name,
        phone_number=phone,
        email=None,
        gender=None,
        marital_status=None,
        first_timer=False,
        connect_name=None,
        date_joined=datetime.now(timezone.utc),
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def upsert_member_by_phone(db: Session, full_name: str, phone: str, aliases: str = ""):
    member = find_member_by_phone(db, phone)
    first_name, last_name = _split_full_name(full_name)
    if member:
        member.first_name = first_name
        member.last_name = last_name
        db.commit()
        db.refresh(member)
        return member, False

    member = models.Member(
        first_name=first_name,
        last_name=last_name,
        phone_number=phone,
        email=None,
        gender=None,
        marital_status=None,
        first_timer=False,
        connect_name=None,
        date_joined=datetime.now(timezone.utc),
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member, True


def create_member_registration(
    db: Session,
    phone_number: str,
    first_name: str,
    last_name: str,
    first_timer: bool,
    gender: str,
    marital_status: str,
    connect_name: str | None = None,
    email: str = "",
):
    member = models.Member(
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        email=email,
        gender=gender,
        marital_status=marital_status,
        first_timer=first_timer,
        connect_name=connect_name,
        date_joined=datetime.now(timezone.utc),
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def get_or_create_connect_group(
    db: Session,
    name: str,
    description: str = "Auto-created from registration",
    meeting_time: str = "TBD",
    meeting_day: str = "TBD",
    service_id: UUID | None = None,
):
    normalized = name.strip()
    if not normalized:
        return None

    row = (
        db.query(models.ConnectGroup)
        .filter(func.lower(models.ConnectGroup.name) == normalized.lower())
        .first()
    )
    if row:
        if service_id and row.service_id != service_id:
            row.service_id = service_id
            db.commit()
            db.refresh(row)
        return row

    row = models.ConnectGroup(
        service_id=service_id,
        name=normalized,
        description=description,
        meeting_time=meeting_time,
        meeting_day=meeting_day,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_or_create_service(
    db: Session,
    service_type: str,
    connect_name: str | None = None,
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


def ensure_service_records_for_registration(
    db: Session,
    service_type: str,
    connect_name: str | None = None,
):
    # Ensure connect group exists first where applicable, then ensure service row exists.
    return get_or_create_service(db, service_type=service_type, connect_name=connect_name)


def mark_attendance(db: Session, member_id):
    today = date.today()
    service = get_or_create_service(db, service_type="sunday_service", connect_name=None)
    att = models.Attendance(
        member_id=member_id,
        service_id=service.id,
        service_type="sunday_service",
        connect_name="",
        service_date=today,
    )
    db.add(att)
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False


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


def has_member_attended_service_before(
    db: Session,
    member_id,
    service_type: str,
    connect_name: str | None = None,
):
    if not inspect(db.bind).has_table("attendance"):
        return False

    normalized_connect = (connect_name or "").strip()
    try:
        query = db.query(models.Attendance).filter(
            models.Attendance.member_id == member_id,
            models.Attendance.service_type == service_type,
        )
        if service_type == "connect":
            query = query.filter(models.Attendance.connect_name == normalized_connect)
        return query.first() is not None
    except ProgrammingError:
        db.rollback()
        return False


def _event_name_for_service(service_type: str, connect_name: str | None = None) -> str:
    if service_type == "connect":
        return connect_name or "connect"
    return service_type


def has_first_timer_event_for_member_today(
    db: Session,
    member_id,
    service_type: str,
    connect_name: str | None = None,
):
    if not inspect(db.bind).has_table("first_timer_events"):
        return False

    today = date.today()
    service_name = _event_name_for_service(service_type, connect_name)
    try:
        row = (
            db.query(models.FirstTimerEvent)
            .filter(
                models.FirstTimerEvent.member_id == member_id,
                models.FirstTimerEvent.service_date == today,
                models.FirstTimerEvent.service_name == service_name,
            )
            .first()
        )
        return row is not None
    except ProgrammingError:
        db.rollback()
        return False


def has_first_timer_event_for_member_today_any_service(
    db: Session,
    member_id,
):
    if not inspect(db.bind).has_table("first_timer_events"):
        return False

    today = date.today()
    try:
        row = (
            db.query(models.FirstTimerEvent)
            .filter(
                models.FirstTimerEvent.member_id == member_id,
                models.FirstTimerEvent.service_date == today,
            )
            .first()
        )
        return row is not None
    except ProgrammingError:
        db.rollback()
        return False


def mark_first_timer_event(
    db: Session,
    member_id,
    service_type: str,
    connect_name: str | None = None,
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



def get_service_types(db: Session) -> List[str]:
    rows = db.query(models.Service.name).distinct().all()
    return [str(r[0]).strip() for r in rows if r and isinstance(r[0], str) and str(r[0]).strip()]


def get_connect_group_names(db: Session) -> List[str]:
    rows = db.query(models.ConnectGroup.name).order_by(models.ConnectGroup.name.asc()).all()
    return [str(r[0]).strip() for r in rows if r and isinstance(r[0], str) and str(r[0]).strip()]


def find_connect_group_by_name(db: Session, name: str):
    normalized = name.strip().lower()
    if not normalized:
        return None
    return (
        db.query(models.ConnectGroup)
        .filter(func.lower(models.ConnectGroup.name) == normalized)
        .first()
    )


def find_connect_group_by_id(db: Session, connect_group_id: UUID):
    return (
        db.query(models.ConnectGroup)
        .filter(models.ConnectGroup.id == connect_group_id)
        .first()
    )


def create_connect_group(
    db: Session,
    name: str,
    description: str,
    meeting_time: str,
    meeting_day: str,
    service_id: UUID | None = None,
):
    row = models.ConnectGroup(
        service_id=service_id,
        name=name.strip(),
        description=description.strip(),
        meeting_time=meeting_time.strip(),
        meeting_day=meeting_day.strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def find_service_by_name(
    db: Session,
    name: str,
):
    return (
        db.query(models.Service)
        .filter(func.lower(models.Service.name) == name.strip().lower())
        .first()
    )


def find_service_by_id(db: Session, service_id: UUID):
    return (
        db.query(models.Service)
        .filter(models.Service.id == service_id)
        .first()
    )


def create_service(
    db: Session,
    name: str,
    theme: str | None = None,
    location: str | None = None,
):
    row = models.Service(
        name=name.strip(),
        theme=(theme or "").strip() or None,
        location=(location or "").strip() or None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def attach_connect_group_to_service(db: Session, connect_group_id: UUID, service_id: UUID):
    row = find_connect_group_by_id(db, connect_group_id)
    if not row:
        return None
    row.service_id = service_id
    db.commit()
    db.refresh(row)
    return row


def register_member_with_attendance_transaction(
    db: Session,
    phone_number: str,
    first_name: str,
    last_name: str,
    email: str,
    gender: str,
    marital_status: str,
    service_type: str,
    connect_name: str | None = None,
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
    except Exception:
        db.rollback()
        raise
