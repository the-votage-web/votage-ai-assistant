
from typing import Optional
import time
import re
import json
from app.common.llm.setup import (
    _BEDROCK_THROTTLE_COOLDOWN_SECONDS,
    PHONE_RE,
    structured_llm,
    extract_prompt,
    llm,
    RAG_PROMPT,
)
from app.common.llm.schemas import Extracted
from pydantic import ValidationError
from app.constants.llm import INTENT_MAP

def extract(message: str) -> Extracted:
    phone = PHONE_RE.search(message)
    _BEDROCK_THROTTLED_UNTIL_TS = 0.0

    if phone:
        message = message + f"\n(Detected phone: {phone.group(0)})"

    if time.time() < _BEDROCK_THROTTLED_UNTIL_TS:
        return _safe_extract("{}", message)

    try:
        result = structured_llm.invoke(
            extract_prompt.format_messages(message=message)
        )
        return result
    except Exception as exc:
        if _is_throttled_error(exc):
            _BEDROCK_THROTTLED_UNTIL_TS = time.time() + _BEDROCK_THROTTLE_COOLDOWN_SECONDS
            # Avoid a second Bedrock call when quota is exhausted.
            return _safe_extract("{}", message)

        # Fallback path: one direct invocation attempt, then pure local heuristic extraction.
        try:
            raw = llm.invoke(extract_prompt.format_messages(message=message))
            content = raw.content if hasattr(raw, "content") else str(raw)
            return _safe_extract(content, message)
        except Exception as raw_exc:
            if _is_throttled_error(raw_exc):
                _BEDROCK_THROTTLED_UNTIL_TS = time.time() + _BEDROCK_THROTTLE_COOLDOWN_SECONDS
            return _safe_extract("{}", message)


def _safe_extract(raw: str, message: str) -> Extracted:
    # First attempt the strict schema.
    try:
        return Extracted.model_validate_json(raw)
    except (ValidationError, ValueError, TypeError):
        pass

    data = _extract_json_obj(raw)
    phone_match = PHONE_RE.search(message)
    phone = str(data.get("phone") or (phone_match.group(0) if phone_match else "")).strip() or None
    full_name = str(data.get("full_name") or "").strip() or None
    sunday_code = str(data.get("sunday_code") or "").strip() or None
    question = str(data.get("question") or "").strip() or None
    service_type = str(data.get("service_type") or "").strip().lower() or None
    if service_type not in {"sunday_service", "connect", "special_service"}:
        service_type = None
    intent = _coerce_intent(
        raw_intent=str(data.get("intent") or "").strip() or None,
        message=message,
        phone=phone,
        question=question,
    )

    return Extracted(
        intent=intent,
        phone=phone,
        full_name=full_name,
        sunday_code=sunday_code,
        question=question,
        service_type=service_type,
    )

def _is_throttled_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        "throttlingexception" in text
        or "too many tokens per day" in text
        or "reached max retries" in text
    )

def _extract_json_obj(raw: str) -> dict:
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _coerce_intent(raw_intent: Optional[str], message: str, phone: Optional[str], question: Optional[str]) -> str:
    if raw_intent:
        mapped = INTENT_MAP.get(raw_intent.strip().lower())
        if mapped:
            return mapped

    lower_msg = message.lower()
    if phone:
        return "checkin"
    if "first" in lower_msg and ("time" in lower_msg or "new" in lower_msg):
        return "first_timer"
    if "update" in lower_msg or "change" in lower_msg:
        return "update_profile"
    if "what should i know about" in lower_msg or "who is" in lower_msg or "who are" in lower_msg:
        return "faq"
    if question or "?" in message:
        return "faq"
    return "unknown"


def generate_answer(question: str, docs: list[str]) -> str:
    """Generate answer from church context using RAG."""
    if not docs:
        return "I don't know. Please contact church admin."

    context = "\n\n".join(docs)
    prompt = RAG_PROMPT.format(context=context, question=question)

    try:
        # We can use LangChain's invoke here for simplicity
        res = llm.invoke(prompt)
        return res.content if hasattr(res, "content") else str(res)
    except Exception as e:
        if _is_throttled_error(e):
             return "I'm a bit busy right now. Please try again in a moment."
        print(f"Error in generate_answer: {e}")
        return "I encountered an error while searching the church knowledge base."