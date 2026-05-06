from uuid import UUID
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import models


def find_connect_group_by_name(db: Session, name: str):
    normalized = name.strip().lower()
    if not normalized:
        return None
    return (
        db.query(models.ConnectGroup)
        .filter(func.lower(models.ConnectGroup.name) == normalized)
        .first()
    )

def create_connect_group(
    db: Session,
    name: str,
    description: str,
    meeting_time: str,
    meeting_day: str,
    service_id: Optional[UUID] = None,
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


