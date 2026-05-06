from typing import List
from uuid import UUID
from typing import Optional
from app.constants.connect import CONNECT_GROUP_ALIASES, CONNECT_GROUPS
from sqlalchemy.orm import Session
from app.db import models
from sqlalchemy import func

def _extract_connect_name(message: str) -> Optional[str]:
    msg = message.lower()
    for alias, canonical in CONNECT_GROUP_ALIASES.items():
        if alias in msg:
            return canonical
    return None

def _connect_group_prompt() -> str:
    options = "\n".join([f"- {name}" for name in CONNECT_GROUPS])
    return f"Great, you selected connect. Please choose your connect group:\n{options}"

def get_or_create_connect_group(
    db: Session,
    name: str,
    description: str = "Auto-created from registration",
    meeting_time: str = "TBD",
    meeting_day: str = "TBD",
    service_id: Optional[UUID] = None
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

def _connect_group_prompt() -> str:
    options = "\n".join([f"- {name}" for name in CONNECT_GROUPS])
    return f"Great, you selected connect. Please choose your connect group:\n{options}"

def get_connect_group_names(db: Session) -> List[str]:
    rows = db.query(models.ConnectGroup.name).order_by(models.ConnectGroup.name.asc()).all()
    return [str(r[0]).strip() for r in rows if r and isinstance(r[0], str) and str(r[0]).strip()]
