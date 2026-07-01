from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.config import settings
from app.services.faq.logs import get_logs, mark_resolved
from app.services.faq.kb import (
    create_kb_entry, list_kb_entries, update_kb_entry, delete_kb_entry,
    render_faq_markdown,
)
from app.services.faq.faq import faq_service

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_admin(x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    expected = settings.ADMIN_API_KEY
    if not expected or x_admin_key != expected:
        raise HTTPException(status_code=403, detail="Admin access required.")


class LoginIn(BaseModel):
    password: str


class KbIn(BaseModel):
    question: str
    answer: str
    from_log_id: Optional[str] = None


@router.post("/admin/login")
def admin_login(payload: LoginIn):
    if not settings.ADMIN_API_KEY or payload.password != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid password.")
    return {"ok": True}


@router.get("/admin/logs")
def admin_logs(status: str = "all", q: Optional[str] = None, limit: int = 100,
               db: Session = Depends(get_db), _admin: None = Depends(require_admin)):
    limit = max(1, min(limit, 500))
    return get_logs(db, status=status, q=q, limit=limit)


@router.get("/admin/kb")
def admin_kb_list(db: Session = Depends(get_db), _admin: None = Depends(require_admin)):
    return list_kb_entries(db)


@router.post("/admin/kb")
def admin_kb_create(payload: KbIn, db: Session = Depends(get_db), _admin: None = Depends(require_admin)):
    try:
        entry = create_kb_entry(db, payload.question, payload.answer)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        faq_service.add_entry(entry)
    except Exception as exc:
        print(f"admin_kb_create: live index update failed (entry saved): {exc!r}")
    if payload.from_log_id:
        mark_resolved(db, payload.from_log_id)
    return entry


@router.put("/admin/kb/{entry_id}")
def admin_kb_update(entry_id: str, payload: KbIn, db: Session = Depends(get_db), _admin: None = Depends(require_admin)):
    try:
        entry = update_kb_entry(db, entry_id, payload.question, payload.answer)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found.")
    try:
        faq_service.update_entry(entry)
    except Exception as exc:
        print(f"admin_kb_update: live index update failed (entry saved): {exc!r}")
    return entry


@router.delete("/admin/kb/{entry_id}")
def admin_kb_delete(entry_id: str, db: Session = Depends(get_db), _admin: None = Depends(require_admin)):
    ok = delete_kb_entry(db, entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Entry not found.")
    try:
        faq_service.remove_entry(entry_id)
    except Exception as exc:
        print(f"admin_kb_delete: live index update failed (row deleted): {exc!r}")
    return {"ok": True}


@router.get("/admin/kb/export")
def admin_kb_export(db: Session = Depends(get_db), _admin: None = Depends(require_admin)):
    seed = faq_service.read_seed_markdown()
    entries = list_kb_entries(db)
    content = render_faq_markdown(seed, entries)
    return PlainTextResponse(
        content,
        headers={"Content-Disposition": 'attachment; filename="faq.md"'},
        media_type="text/markdown",
    )
