from typing import List
from typing import Optional
from app.constants.service import SERVICE_KEYWORDS
from app.db import models
from sqlalchemy.orm import Session

def _event_name_for_service(service_type: str, connect_name: str | None = None) -> str:
    if service_type == "connect":
        return connect_name or "connect"
    return service_type

def _extract_service_type(message: str, extracted_service_type: Optional[str]) -> Optional[str]:
    if extracted_service_type in {"sunday_service", "connect", "special_service"}:
        return extracted_service_type
    msg = message.lower()
    for key, value in SERVICE_KEYWORDS.items():
        if key in msg:
            return value
    return None

def _service_type_prompt() -> str:
    return (
        "Please choose a service type to complete check-in:\n"
        "- sunday_service\n"
        "- connect\n"
        "- special_service"
    )

def get_service_types(db: Session) -> List[str]:
    rows = db.query(models.Service.name).distinct().all()
    return [str(r[0]).strip() for r in rows if r and isinstance(r[0], str) and str(r[0]).strip()]
