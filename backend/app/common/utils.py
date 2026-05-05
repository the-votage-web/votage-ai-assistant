import re
from app.db.config import settings
from sqlalchemy.orm import Session
from typing import Optional
from app.db import models
try:
    import phonenumbers
    from phonenumbers import NumberParseException
except Exception:  # pragma: no cover - optional dependency
    phonenumbers = None
    NumberParseException = Exception


def normalize_phone(phone: str) -> tuple[Optional[str], Optional[str]]:
    raw = (phone or "").strip()
    if not raw:
        return None, None

    if raw.startswith("00"):
        raw = f"+{raw[2:]}"

    digits = _digits_only(raw)
    last10 = digits[-10:] if len(digits) >= 10 else (digits or None)

    if phonenumbers:
        try:
            if raw.startswith("+"):
                number = phonenumbers.parse(raw, None)
            else:
                default_region = getattr(settings, "DEFAULT_PHONE_REGION", "NG")
                number = phonenumbers.parse(raw, default_region)
            if phonenumbers.is_valid_number(number):
                e164 = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
                last10 = _digits_only(e164)[-10:]
                return e164, last10
        except NumberParseException:
            pass

    return None, last10

def find_member_by_phone(db: Session, phone: str):
    if not phone:
        return None

    exact = db.query(models.Member).filter(models.Member.phone_number == phone).first()
    if exact:
        return exact

    e164, last10 = normalize_phone(phone)
    if not e164 and not last10:
        return None

    if not last10:
        return None

    candidates = (
        db.query(models.Member)
        .filter(models.Member.phone_number.like(f"%{last10}"))
        .all()
    )
    for member in candidates:
        mem_e164, mem_last10 = normalize_phone(member.phone_number)
        if e164 and mem_e164 and mem_e164 == e164:
            return member
        if mem_last10 and mem_last10 == last10:
            return member
    return None

def _digits_only(value: str) -> str:
    return re.sub(r"\\D", "", value or "")
