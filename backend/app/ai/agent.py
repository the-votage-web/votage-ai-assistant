import re
import json
import time
from dotenv import load_dotenv
load_dotenv()  # loads API key and other env vars

import os
from typing import Optional
from pathlib import Path
from sqlalchemy.orm import Session
from pydantic import ValidationError

# from langchain_community.llms import Ollama
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings
from app.ai.schemas import Extracted
from app.db import crud
from app.rag.chroma_store import docs_store, members_store

from langchain_aws.chat_models import ChatBedrock



PHONE_RE = re.compile(r"\b0\d{10}\b")  # simple NG pattern
INTENT_MAP = {
    "checkin": "checkin",
    "check_in": "checkin",
    "check-in": "checkin",
    "attendance": "checkin",
    "phone": "checkin",
    "first_timer": "first_timer",
    "firsttimer": "first_timer",
    "first time": "first_timer",
    "new": "first_timer",
    "faq": "faq",
    "question": "faq",
    "update_profile": "update_profile",
    "update profile": "update_profile",
    "update": "update_profile",
    "unknown": "unknown",
}
SERVICE_KEYWORDS = {
    "sunday": "sunday_service",
    "sunday_service": "sunday_service",
    "connect": "connect",
    "special": "special_service",
    "special_service": "special_service",
}
CONNECT_GROUPS = [
    "KABOD CONNECT",
    "NEWNESS CONNECT",
    "UGBOWO CONNECT",
    "FLOURISH CONNECT",
    "GATEKEEPERS CONNECT",
    "KOINONIA CONNECT",
    "EKEHUAN CONNECT",
]
CONNECT_GROUP_ALIASES = {
    "kabod": "KABOD CONNECT",
    "newness": "NEWNESS CONNECT",
    "ugbowo": "UGBOWO CONNECT",
    "flourish": "FLOURISH CONNECT",
    "gatekeepers": "GATEKEEPERS CONNECT",
    "koinonia": "KOINONIA CONNECT",
    "koinoinia": "KOINONIA CONNECT",
    "ekehuan": "EKEHUAN CONNECT",
}
GREETING_TOKENS = {
    "hi",
    "hello",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
}
FAQ_SESSION_START_TOKENS = {
    "faq",
    "start faq",
    "faq session",
    "start faq session",
    "start qna",
}
FAQ_SESSION_END_TOKENS = {
    "exit faq",
    "end faq",
    "stop faq",
    "close faq",
}

# llm = Ollama(base_url=settings.OLLAMA_BASE_URL, model=settings.LLM_MODEL)
STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "is",
    "are", "do", "does", "did", "what", "who", "where", "when", "why", "how",
    "your", "you", "about", "know", "tell", "me",
}

extract_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are an AI church assistant. Extract the user's intent and fields.\n"
     "Extract the user's intent and fields. Follow the schema exactly.If a field is missing, return null.\n"
     "{{intent: one of [checkin, first_timer, faq, update_profile, unknown], "
     "phone?: string, full_name?: string, sunday_code?: string, question?: string, "
     "service_type?: one of [sunday_service, connect, special_service]}}\n"
     "Rules:\n"
     "- If user wants to mark attendance -> intent=checkin.\n"
     "- If user says first time/new -> intent=first_timer.\n"
     "- If user asks church info -> intent=faq and put the question.\n"
     "- If user mentions updating phone/name -> intent=update_profile.\n"
     "- If user mentions sunday/connect/special service during checkin, extract service_type.\n"
    ),
    ("user", "{message}")
])

faq_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a helpful church assistant. Answer using ONLY the context. "
     "If the context doesn't contain the answer, say you don't know and suggest contacting an admin.\n"
     "Keep it short and clear."
    ),
    ("user", "Question: {question}\n\nContext:\n{context}")
])
FAQ_BLOCK_RE = re.compile(
    r"Q:\s*(?P<question>.+?)\nA:\s*(?P<answer>.+?)(?=\nQ:|\n##\s+Sources|\Z)",
    re.DOTALL,
)

_bedrock_model_id = os.getenv("BEDROCK_PROFILE_ARN") or os.getenv("BEDROCK_MODEL_ID")
_bedrock_provider = os.getenv("BEDROCK_PROVIDER", "anthropic")

if not _bedrock_model_id:
    raise RuntimeError("Set BEDROCK_MODEL_ID or BEDROCK_PROFILE_ARN in environment variables.")

llm = ChatBedrock(
    model_id=_bedrock_model_id,
    region_name=os.getenv("AWS_REGION"),
    provider=_bedrock_provider,
)

structured_llm = llm.with_structured_output(Extracted)
_BEDROCK_THROTTLED_UNTIL_TS = 0.0
_BEDROCK_THROTTLE_COOLDOWN_SECONDS = int(os.getenv("BEDROCK_THROTTLE_COOLDOWN_SECONDS", "600"))


def _is_throttled_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        "throttlingexception" in text
        or "too many tokens per day" in text
        or "reached max retries" in text
    )

def extract(message: str) -> Extracted:
    global _BEDROCK_THROTTLED_UNTIL_TS
    phone = PHONE_RE.search(message)

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


def _extract_service_type(message: str, extracted_service_type: Optional[str]) -> Optional[str]:
    if extracted_service_type in {"sunday_service", "connect", "special_service"}:
        return extracted_service_type
    msg = message.lower()
    for key, value in SERVICE_KEYWORDS.items():
        if key in msg:
            return value
    return None


def _load_state(raw_state: str) -> dict:
    try:
        data = json.loads(raw_state or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_state(db: Session, chat_session, state: dict) -> None:
    chat_session.state_json = json.dumps(state)
    db.commit()


def _service_type_prompt() -> str:
    return (
        "Please choose a service type to complete check-in:\n"
        "- sunday_service\n"
        "- connect\n"
        "- special_service"
    )


def _connect_group_prompt() -> str:
    options = "\n".join([f"- {name}" for name in CONNECT_GROUPS])
    return f"Great, you selected connect. Please choose your connect group:\n{options}"


def _default_welcome_message() -> str:
    return (
        "Hi 👋 I’m the church assistant.\n\n"
        "Tap a quick action button below to get started (Check-in or FAQ).\n\n"
        "• To check in: send your phone number (e.g. 08012345678)\n"
        "• To ask: “What time is service?”"
    )


def _is_greeting_message(message: str) -> bool:
    normalized = re.sub(r"\s+", " ", message.lower()).strip()
    return normalized in GREETING_TOKENS


def _is_faq_session_start_message(message: str) -> bool:
    normalized = re.sub(r"\s+", " ", message.lower()).strip()
    return normalized in FAQ_SESSION_START_TOKENS


def _is_faq_session_end_message(message: str) -> bool:
    normalized = re.sub(r"\s+", " ", message.lower()).strip()
    return normalized in FAQ_SESSION_END_TOKENS


def _is_end_session_message(message: str) -> bool:
    normalized = re.sub(r"\s+", " ", message.lower()).strip()
    return normalized in {"end", "stop", "cancel", "quit", "end session", "stop session", "cancel session"}


def _is_successful_checkin_response(text: str) -> bool:
    return text.startswith("✅") or text.startswith("👌")


def _extract_connect_name(message: str) -> Optional[str]:
    msg = message.lower()
    for alias, canonical in CONNECT_GROUP_ALIASES.items():
        if alias in msg:
            return canonical
    return None


def _record_checkin(db: Session, phone: str, service_type: str, connect_name: Optional[str] = None) -> str:
    member = crud.find_member_by_phone(db, phone)
    if not member:
        return (
            "👋 I don’t recognize that phone number yet.\n"
            f"Please register here first: {settings.REGISTRATION_PAGE_URL}"
        )

    member_display_name = f"{member.first_name} {member.last_name}".strip()
    effective_connect_name = connect_name if service_type == "connect" else None
    if service_type == "connect" and member.connect_name:
        registered_connect = member.connect_name.strip()
        selected_connect = (effective_connect_name or "").strip()
        if registered_connect and selected_connect and registered_connect.lower() != selected_connect.lower():
            return (
                "❌ Connect check-in failed. "
                f"Your registration is under {registered_connect}. "
                f"You selected {selected_connect}. "
                "Please select your registered connect group or contact an admin to update your profile.\n\n"
                f"{_connect_group_prompt()}"
            )

    new = crud.mark_attendance_for_service(
        db,
        member.id,
        service_type,
        connect_name=effective_connect_name,
    )
    if member.first_timer:
        crud.mark_first_timer_event(
            db=db,
            member_id=member.id,
            service_type=service_type,
            connect_name=effective_connect_name or member.connect_name,
        )

    service_label = service_type.replace("_", " ")
    if service_type == "connect" and effective_connect_name:
        service_label = f"connect ({effective_connect_name})"

    if new:
        return f"✅ Attendance recorded for {service_label}. Welcome, {member_display_name}! 🙏"

    if service_type == "connect":
        existing = crud.get_attendance_for_member_service_today(db, member.id, "connect")
        existing_connect_name = (existing.connect_name or "").strip() if existing else ""
        if existing_connect_name:
            service_label = f"connect ({existing_connect_name})"
        else:
            service_label = "connect"
    return f"👌 You’re already checked in for {service_label} today, {member_display_name}."


def _normalize_token(token: str) -> str:
    t = token.lower().strip()
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("s"):
        return t[:-1]
    return t


def _keywords(text: str) -> set[str]:
    raw = re.findall(r"[a-zA-Z0-9']+", text.lower())
    return {
        _normalize_token(t)
        for t in raw
        if len(t) > 2 and _normalize_token(t) not in STOPWORDS
    }


def _rerank_by_keyword_overlap(question: str, docs):
    q_tokens = _keywords(question)
    if not q_tokens:
        return docs

    scored = []
    for d in docs:
        content_tokens = _keywords(d.page_content)
        overlap = len(q_tokens.intersection(content_tokens))
        scored.append((overlap, d))

    scored.sort(key=lambda x: x[0], reverse=True)
    if scored and scored[0][0] > 0:
        return [d for _, d in scored]
    return docs


def _best_doc_and_score(question: str, docs):
    q_tokens = _keywords(question)
    if not q_tokens:
        return None, 0

    best_doc = None
    best_score = 0
    for d in docs:
        content_tokens = _keywords(d.page_content)
        score = len(q_tokens.intersection(content_tokens))
        if score > best_score:
            best_doc = d
            best_score = score

    return best_doc, best_score


def _extract_answer_from_doc(doc_text: str) -> str:
    match = re.search(r"\bA:\s*(.+)", doc_text, flags=re.DOTALL)
    if not match:
        return doc_text.strip()
    return match.group(1).strip()


def _load_faq_pairs_from_markdown() -> list[tuple[str, str]]:
    faq_path = Path(__file__).resolve().parents[1] / "rag" / "church_faq.md"
    if not faq_path.exists():
        return []
    text = faq_path.read_text(encoding="utf-8")
    pairs: list[tuple[str, str]] = []
    for m in FAQ_BLOCK_RE.finditer(text):
        q = m.group("question").strip()
        a = re.sub(r"\s+", " ", m.group("answer")).strip()
        if q and a:
            pairs.append((q, a))
    return pairs


def _fallback_answer_from_markdown(question: str) -> Optional[str]:
    q_tokens = _keywords(question)
    if not q_tokens:
        return None

    best_answer = None
    best_score = 0
    for q, a in _load_faq_pairs_from_markdown():
        cand_tokens = _keywords(q)
        score = len(q_tokens.intersection(cand_tokens))
        if score > best_score:
            best_score = score
            best_answer = a

    min_score = 2 if len(q_tokens) >= 3 else 1
    if best_score >= min_score:
        return best_answer
    return None


def _normalize_question_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _answer_from_markdown_preferred(question: str) -> Optional[str]:
    pairs = _load_faq_pairs_from_markdown()
    if not pairs:
        return None

    normalized_query = _normalize_question_text(question)
    query_mentions_plural_pastors = "pastors" in normalized_query or "lead pastors" in normalized_query
    query_mentions_address = any(
        token in normalized_query
        for token in ["address", "location", "where", "find us", "airport road", "benin"]
    )
    q_tokens = _keywords(question)
    if not normalized_query or not q_tokens:
        return None

    best_answer = None
    best_question = None
    best_score = 0.0
    for q, a in pairs:
        normalized_q = _normalize_question_text(q)
        cand_tokens = _keywords(q)
        overlap = len(q_tokens.intersection(cand_tokens))
        precision = overlap / max(1, len(q_tokens))
        recall = overlap / max(1, len(cand_tokens))
        score = (2 * precision * recall) / max(0.0001, precision + recall)  # F1

        # Generic "connect" queries should prefer overview answers, not subgroup schedules.
        if "connect" in q_tokens:
            if {"system", "group"}.intersection(cand_tokens):
                score += 0.25
            if {"kabod", "newness", "ugbowo", "flourish", "gatekeepers", "koinonia", "ekehuan"}.intersection(cand_tokens):
                score -= 0.15

        # Collective pastor queries should prefer the lead-pastors summary over individual bios.
        if query_mentions_plural_pastors and "pastor" in cand_tokens:
            if "lead" in cand_tokens:
                score += 0.35
            if {"rev", "ohis", "anwinli", "ojeikere"}.intersection(cand_tokens):
                score -= 0.1

        # Address/location queries should prioritize address/location questions.
        if query_mentions_address:
            if {"address", "location", "find", "church", "votage"}.intersection(cand_tokens):
                score += 0.3
            if {"compelled", "love", "reach", "global", "ministry", "vision", "mission"}.intersection(cand_tokens):
                score -= 0.2

        if normalized_query == normalized_q:
            return a
        if normalized_query in normalized_q and precision >= 0.7:
            return a
        if score > best_score:
            best_score = score
            best_answer = a
            best_question = q

    # For short queries (e.g. "connect"), one strong token hit is often enough.
    if len(q_tokens) <= 2 and best_question:
        best_tokens = _keywords(best_question)
        if len(q_tokens.intersection(best_tokens)) >= 1:
            return best_answer
    if best_score >= 0.55:
        return best_answer
    return None


def _markdown_best_match(question: str) -> tuple[Optional[str], Optional[str], float]:
    pairs = _load_faq_pairs_from_markdown()
    if not pairs:
        return None, None, 0.0
    q_tokens = _keywords(question)
    if not q_tokens:
        return None, None, 0.0

    best_q: Optional[str] = None
    best_a: Optional[str] = None
    best_score = 0.0
    for q, a in pairs:
        cand_tokens = _keywords(q)
        overlap = len(q_tokens.intersection(cand_tokens))
        precision = overlap / max(1, len(q_tokens))
        recall = overlap / max(1, len(cand_tokens))
        score = (2 * precision * recall) / max(0.0001, precision + recall)
        if score > best_score:
            best_score = score
            best_q = q
            best_a = a
    return best_q, best_a, best_score


def debug_faq_match(question: str) -> dict:
    matched_q, matched_a, md_score = _markdown_best_match(question)
    preferred = _answer_from_markdown_preferred(question)
    result = {
        "question": question,
        "method": "unknown",
        "matched_question": matched_q,
        "score": round(md_score, 4),
        "answer_preview": (preferred or matched_a or "")[:240],
    }
    if preferred:
        result["method"] = "markdown_preferred"
        return result

    try:
        store = docs_store()
        docs = store.similarity_search(question, k=5, filter={"doc_type": "faq_qa"})
        docs = _rerank_by_keyword_overlap(question, docs)
        best_doc, best_score = _best_doc_and_score(question, docs)
        if best_doc:
            result["method"] = "vector_fallback"
            result["score"] = best_score
            result["answer_preview"] = _extract_answer_from_doc(best_doc.page_content)[:240]
        else:
            result["method"] = "no_match"
    except Exception:
        result["method"] = "vector_error"
    return result


def rag_answer_faq(question: str) -> str:
    try:
        preferred = _answer_from_markdown_preferred(question)
        if preferred:
            return preferred

        store = docs_store()
        docs = store.similarity_search(question, k=10, filter={"doc_type": "faq_qa"})
        if not docs:
            fallback = _fallback_answer_from_markdown(question)
            if fallback:
                return fallback
            return "I don't know. Would you like to contact an admin for more information?"

        docs = _rerank_by_keyword_overlap(question, docs)
        best_doc, best_score = _best_doc_and_score(question, docs)
        if not best_doc:
            return "I don't know. Would you like to contact an admin for more information?"

        q_tokens = _keywords(question)
        min_score = 2 if len(q_tokens) >= 3 else 1
        if best_score < min_score:
            fallback = _fallback_answer_from_markdown(question)
            if fallback:
                return fallback
            return "I don't know. Would you like to contact an admin for more information?"

        answer = _extract_answer_from_doc(best_doc.page_content)
        if not answer:
            return "I don't know. Would you like to contact an admin for more information?"
        return answer
    except Exception:
        fallback = _fallback_answer_from_markdown(question)
        if fallback:
            return fallback
        return (
            "I can't access the church knowledge base right now. "
            "Please contact an admin, or try again after embeddings are configured."
        )

def member_candidates_by_name(name_query: str):
    store = members_store()
    # member docs are stored as text; similarity search returns Documents
    docs = store.similarity_search(name_query, k=3)
    return docs

def upsert_member_vector(member_id: str, full_name: str, phone: str, aliases: str = ""):
    store = members_store()
    doc = f"Name: {full_name}\nPhone: {phone}\nAliases: {aliases}".strip()
    store.add_texts([doc], metadatas=[{"member_id": member_id}])
    if hasattr(store, "persist"):
        store.persist()

def handle_message(db: Session, session_id: str, message: str) -> str:
    chat_session = crud.get_or_create_session(db, session_id)
    state = _load_state(chat_session.state_json)

    if _is_end_session_message(message):
        state.pop("pending_checkin_phone", None)
        state.pop("pending_service_type", None)
        state.pop("faq_session", None)
        _save_state(db, chat_session, state)
        return "Session ended. If you want to check in again, send your phone number."

    if _is_faq_session_start_message(message):
        state["faq_session"] = True
        state.pop("pending_checkin_phone", None)
        state.pop("pending_service_type", None)
        _save_state(db, chat_session, state)
        return "FAQ session started. Ask me any church question."

    if _is_faq_session_end_message(message):
        state.pop("faq_session", None)
        _save_state(db, chat_session, state)
        return _default_welcome_message()

    ex = extract(message)
    pending_phone = state.get("pending_checkin_phone")
    pending_service_type = state.get("pending_service_type")
    faq_session = bool(state.get("faq_session"))

    if pending_phone:
        if ex.phone:
            pending_phone = ex.phone
            state["pending_checkin_phone"] = pending_phone
            _save_state(db, chat_session, state)

        if pending_service_type == "connect":
            chosen_connect_name = _extract_connect_name(message)
            if not chosen_connect_name:
                return _connect_group_prompt()

            response = _record_checkin(
                db,
                pending_phone,
                "connect",
                connect_name=chosen_connect_name,
            )
            if _is_successful_checkin_response(response):
                state.pop("pending_checkin_phone", None)
                state.pop("pending_service_type", None)
                _save_state(db, chat_session, state)
            else:
                state["pending_checkin_phone"] = pending_phone
                state["pending_service_type"] = "connect"
                _save_state(db, chat_session, state)
            return response

        chosen_service_type = _extract_service_type(message, ex.service_type)
        if not chosen_service_type:
            return _service_type_prompt()

        if chosen_service_type == "connect":
            state["pending_service_type"] = "connect"
            _save_state(db, chat_session, state)
            return _connect_group_prompt()

        response = _record_checkin(db, pending_phone, chosen_service_type)
        if _is_successful_checkin_response(response):
            state.pop("pending_checkin_phone", None)
            state.pop("pending_service_type", None)
            _save_state(db, chat_session, state)
        else:
            state["pending_checkin_phone"] = pending_phone
            state.pop("pending_service_type", None)
            _save_state(db, chat_session, state)
        return response

    if faq_session:
        if ex.intent in {"checkin", "first_timer", "update_profile"}:
            state.pop("faq_session", None)
            _save_state(db, chat_session, state)
        else:
            return rag_answer_faq(ex.question or message)

    if _is_greeting_message(message):
        return _default_welcome_message()

    # FAQ
    if ex.intent == "faq":
        q = ex.question or message
        return rag_answer_faq(q)

    # First timer
    if ex.intent == "first_timer":
        return (
            "👋 Welcome! Please register once here:\n"
            f"{settings.REGISTRATION_PAGE_URL}"
        )

    # Check-in
    if ex.intent == "checkin":
        # Optional MVP anti-fraud
        if settings.SUNDAY_CODE and ex.sunday_code and ex.sunday_code != settings.SUNDAY_CODE:
            return "❌ That Sunday code is incorrect. Please check the code announced in church."

        phone = ex.phone
        service_type = _extract_service_type(message, ex.service_type)
        # If user didn't provide phone, ask
        if not phone:
            # if they provided a name, try vector search suggestions
            if ex.full_name:
                cands = member_candidates_by_name(ex.full_name)
                if cands:
                    preview = "\n".join([f"- {d.page_content.splitlines()[0].replace('Name: ', '')}" for d in cands])
                    return (
                        "I can help you check in, but I need your phone number.\n"
                        "I found these similar names:\n"
                        f"{preview}\n\n"
                        "Please send your phone number (e.g. 08012345678)."
                    )
            return (
                "Please send your phone number (e.g. 08012345678) to check in.\n"
            )

        if not service_type:
            state["pending_checkin_phone"] = phone
            state.pop("pending_service_type", None)
            _save_state(db, chat_session, state)
            return _service_type_prompt()

        if service_type == "connect":
            chosen_connect_name = _extract_connect_name(message)
            if not chosen_connect_name:
                state["pending_checkin_phone"] = phone
                state["pending_service_type"] = "connect"
                _save_state(db, chat_session, state)
                return _connect_group_prompt()

            response = _record_checkin(db, phone, "connect", connect_name=chosen_connect_name)
            if _is_successful_checkin_response(response):
                state.pop("pending_checkin_phone", None)
                state.pop("pending_service_type", None)
                _save_state(db, chat_session, state)
            else:
                state["pending_checkin_phone"] = phone
                state["pending_service_type"] = "connect"
                _save_state(db, chat_session, state)
            return response

        response = _record_checkin(db, phone, service_type)
        if _is_successful_checkin_response(response):
            state.pop("pending_checkin_phone", None)
            state.pop("pending_service_type", None)
            _save_state(db, chat_session, state)
        else:
            state["pending_checkin_phone"] = phone
            state.pop("pending_service_type", None)
            _save_state(db, chat_session, state)
        return response

    # Update profile (MVP: ask them to contact admin or fill form)
    if ex.intent == "update_profile":
        return "To update your details, please contact an admin or fill the first-timer form again with your correct details."

    return (
        _default_welcome_message()
    )
