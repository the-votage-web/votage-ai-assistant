"""Capture failed registrations and check-ins for admin review.

Defensive: logging must never break the visitor's flow (mirrors faq/logs.py).
The pure helper derive_reason is import-safe for unit testing.
"""
import uuid
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import IntakeIssue

MAX_MESSAGE_LEN = 4000


def derive_reason(kind: str, http_status: Optional[int]) -> str:
    """Map an HTTP status to a stable reason code for client-reported errors."""
    if http_status == 409:
        return "phone_exists" if kind == "registration" else "duplicate"
    if http_status == 422:
        return "validation_error"
    if http_status is not None and http_status >= 500:
        return "server_error"
    return "ui_error"


def _clip(text: Optional[str]) -> Optional[str]:
    return text[:MAX_MESSAGE_LEN] if text else text


def _full_name(details: Dict[str, Any]) -> Optional[str]:
    first = str(details.get("first_name") or "").strip()
    last = str(details.get("last_name") or "").strip()
    full = f"{first} {last}".strip()
    return full or None


def _insert(db: Session, **fields) -> None:
    db.add(IntakeIssue(id=uuid.uuid4(), **fields))
    db.commit()


def report_intake_issue(kind: str, message: str, http_status: Optional[int] = None,
                        details: Optional[Dict[str, Any]] = None,
                        session_id: Optional[str] = None) -> None:
    """Insert a client-reported UI error. Own session; never raises."""
    details = details or {}
    kind = kind if kind in ("checkin", "registration") else "registration"
    try:
        db = SessionLocal()
        try:
            _insert(
                db,
                kind=kind,
                reason=derive_reason(kind, http_status),
                message=_clip(message),
                source="client",
                http_status=http_status,
                phone=_clip(details.get("phone_number") or details.get("phone")),
                email=_clip(details.get("email")),
                name=_clip(_full_name(details)),
                details=_clip(json.dumps(details)),
                session_id=session_id,
            )
        finally:
            db.close()
    except Exception as exc:
        print(f"report_intake_issue failed: {exc!r}")


def log_checkin_failure(session_id: Optional[str], reason: str, message: str,
                        phone: Optional[str], service_type: Optional[str] = None,
                        connect_name: Optional[str] = None) -> None:
    """Insert a server-side check-in dead-end. Own session; never raises."""
    try:
        db = SessionLocal()
        try:
            _insert(
                db,
                kind="checkin",
                reason=reason,
                message=_clip(message),
                source="server",
                http_status=None,
                phone=_clip(phone),
                email=None,
                name=None,
                details=json.dumps({"phone": phone, "service_type": service_type, "connect_name": connect_name}),
                session_id=session_id,
            )
        finally:
            db.close()
    except Exception as exc:
        print(f"log_checkin_failure failed: {exc!r}")


def _to_dict(r: IntakeIssue) -> Dict:
    return {
        "id": str(r.id),
        "kind": r.kind,
        "reason": r.reason,
        "message": r.message,
        "source": r.source,
        "http_status": r.http_status,
        "phone": r.phone,
        "email": r.email,
        "name": r.name,
        "session_id": r.session_id,
        "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def get_intake_issues(db: Session, kind: str = "all", q: Optional[str] = None,
                      limit: int = 100) -> List[Dict]:
    query = db.query(IntakeIssue)
    if kind in ("checkin", "registration"):
        query = query.filter(IntakeIssue.kind == kind)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            IntakeIssue.phone.ilike(like),
            IntakeIssue.email.ilike(like),
            IntakeIssue.name.ilike(like),
            IntakeIssue.message.ilike(like),
        ))
    rows = query.order_by(IntakeIssue.created_at.desc()).limit(limit).all()
    return [_to_dict(r) for r in rows]


def mark_intake_resolved(db: Session, issue_id: str) -> bool:
    try:
        row = db.query(IntakeIssue).filter(IntakeIssue.id == issue_id).first()
        if not row:
            return False
        row.resolved_at = datetime.now(timezone.utc)
        db.commit()
        return True
    except Exception as exc:
        db.rollback()
        print(f"mark_intake_resolved failed: {exc!r}")
        return False
