from sqlalchemy.orm import Session
from sqlalchemy.exc import ProgrammingError
from sqlalchemy import inspect
from datetime import date
from typing import Optional
from app.db import models
from app.common.service import _event_name_for_service


def has_first_timer_event_for_member_today(
    db: Session,
    member_id,
    service_type: str,
    connect_name: Optional[str] = None
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