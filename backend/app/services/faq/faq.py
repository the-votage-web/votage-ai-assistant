from sqlalchemy.orm import Session
from app.common.state import _load_state, _save_state
from app.common.session import get_or_create_session, _is_end_session_message, _is_faq_session_start_message, _is_faq_session_end_message
from app.common.llm.llm import extract
from app.services.faq.crud import rag_answer_faq, _markdown_best_match, _answer_from_markdown_preferred
from app.services.faq.utils import _is_greeting_message, _rerank_by_keyword_overlap, _best_doc_and_score, _extract_answer_from_doc
from app.db.config import settings
from app.rag.store import docs_store


def handle_faq(db: Session, session_id: str, message: str) -> str:
    chat_session = get_or_create_session(db, session_id)
    state = _load_state(chat_session.state_json)

    if _is_end_session_message(message):
        state.pop("faq_session", None)
        _save_state(db, chat_session, state)
        return "Session ended. How else can I help you today?"

    if _is_faq_session_start_message(message):
        state["faq_session"] = True
        _save_state(db, chat_session, state)
        return "FAQ session started. Ask me any church question."

    if _is_faq_session_end_message(message):
        state.pop("faq_session", None)
        _save_state(db, chat_session, state)
        return "I've closed the FAQ session. What else would you like to know?"

    ex = extract(message)
    faq_session = bool(state.get("faq_session"))

    if faq_session:
        return rag_answer_faq(ex.question or message)

    if _is_greeting_message(message):
        return (
            "Hi 👋 I’m the church FAQ assistant. I'm here to help with any questions you have about our services and events.\n\n"
            "You can ask me things like: “What time is service?” or “How do I join a connect group?”"
        )

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

    # Update profile
    if ex.intent == "update_profile":
        return "To update your details, please contact an admin or fill the first-timer form again with your correct details."

    # If they tried to check-in here, gently redirect them
    if ex.intent == "checkin":
        return (
            "I'm sorry, I can only help with FAQ here. "
            "For check-in, please visit our [Registration Page](https://votage.church/register)."
        )

    return (
        "I’m not sure how to help with that. I'm here for FAQ and general info.\n\n"
        "Try asking: “What time is service?”"
    )

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