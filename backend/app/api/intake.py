from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.services.intake.logs import report_intake_issue

router = APIRouter()


class IssueReportIn(BaseModel):
    kind: str
    message: str
    http_status: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None


@router.post("/intake-issues/report")
def report_issue(payload: IssueReportIn):
    """Public: the frontend reports the exact error a visitor saw. Best-effort."""
    report_intake_issue(
        kind=payload.kind,
        message=payload.message,
        http_status=payload.http_status,
        details=payload.details,
        session_id=payload.session_id,
    )
    return {"ok": True}
