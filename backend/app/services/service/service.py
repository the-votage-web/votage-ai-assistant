from uuid import UUID
from typing import Optional
from sqlalchemy.orm import Session
from app.db import models
from sqlalchemy import func


def find_service_by_name(
    db: Session,
    name: str,
):
    return (
        db.query(models.Service)
        .filter(func.lower(models.Service.name) == name.strip().lower())
        .first()
    )


def create_service(
    db: Session,
    name: str,
    theme: Optional[str] = None,
    location: Optional[str] = None
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

def find_service_by_id(db: Session, service_id: UUID):
    return (
        db.query(models.Service)
        .filter(models.Service.id == service_id)
        .first()
    )

