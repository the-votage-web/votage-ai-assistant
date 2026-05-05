from typing import Optional
from sqlalchemy.orm import Session
from app.common import session, state, connect
from app.common.llm.llm import extract
from app.services.checkin.crud import mark_attendance_for_service, mark_first_timer_event, get_attendance_for_member_service_today
from app.db.config import settings
from app.services.checkin.utils import _is_successful_checkin_response
from app.common.service import _extract_service_type, _service_type_prompt
from app.common.utils import find_member_by_phone

def handle_checkin(db: Session, session_id: str, message: str) -> str:
    chat_session = session.get_or_create_session(db, session_id)
    chat_state = state._load_state(chat_session.state_json)

    if session._is_end_session_message(message):
        chat_state.pop("pending_checkin_phone", None)
        chat_state.pop("pending_service_type", None)
        state._save_state(db, chat_session, chat_state)
        return "Check-in session ended."

    ex = extract(message)
    pending_phone = chat_state.get("pending_checkin_phone")
    pending_service_type = chat_state.get("pending_service_type")

    # 1. Continue existing check-in flow
    if pending_phone:
        if ex.phone:
            pending_phone = ex.phone
            chat_state["pending_checkin_phone"] = pending_phone
            state._save_state(db, chat_session, chat_state)

        if pending_service_type == "connect":
            chosen_connect_name = connect._extract_connect_name(message)
            if not chosen_connect_name:
                return connect._connect_group_prompt()

            response = _record_checkin(
                db,
                pending_phone,
                "connect",
                connect_name=chosen_connect_name,
            )
            if _is_successful_checkin_response(response):
                chat_state.pop("pending_checkin_phone", None)
                chat_state.pop("pending_service_type", None)
            else:
                chat_state["pending_checkin_phone"] = pending_phone
                chat_state["pending_service_type"] = "connect"
            state._save_state(db, chat_session, chat_state)
            return response

        chosen_service_type = _extract_service_type(message, ex.service_type)
        if not chosen_service_type:
            return _service_type_prompt()

        if chosen_service_type == "connect":
            chat_state["pending_service_type"] = "connect"
            state._save_state(db, chat_session, chat_state)
            return connect._connect_group_prompt()

        response = _record_checkin(db, pending_phone, chosen_service_type)
        if _is_successful_checkin_response(response):
            chat_state.pop("pending_checkin_phone", None)
            chat_state.pop("pending_service_type", None)
        else:
            chat_state["pending_checkin_phone"] = pending_phone
            chat_state.pop("pending_service_type", None)
        state._save_state(db, chat_session, chat_state)
        return response

    # 2. Start new check-in flow
    if ex.intent == "checkin":
        phone = ex.phone
        service_type = _extract_service_type(message, ex.service_type)
        
        # If user didn't provide phone, ask
        if not phone:
            return "Please send your phone number (e.g. 08012345678) to check in."

        if not service_type:
            chat_state["pending_checkin_phone"] = phone
            chat_state.pop("pending_service_type", None)
            state._save_state(db, chat_session, chat_state)
            return _service_type_prompt()

        if service_type == "connect":
            chosen_connect_name = connect._extract_connect_name(message)
            if not chosen_connect_name:
                chat_state["pending_checkin_phone"] = phone
                chat_state["pending_service_type"] = "connect"
                state._save_state(db, chat_session, chat_state)
                return connect._connect_group_prompt()

            response = _record_checkin(db, phone, "connect", connect_name=chosen_connect_name)
            if _is_successful_checkin_response(response):
                chat_state.pop("pending_checkin_phone", None)
                chat_state.pop("pending_service_type", None)
            else:
                chat_state["pending_checkin_phone"] = phone
                chat_state["pending_service_type"] = "connect"
            state._save_state(db, chat_session, chat_state)
            return response

        response = _record_checkin(db, phone, service_type)
        if _is_successful_checkin_response(response):
            chat_state.pop("pending_checkin_phone", None)
            chat_state.pop("pending_service_type", None)
        else:
            chat_state["pending_checkin_phone"] = phone
            chat_state.pop("pending_service_type", None)
        state._save_state(db, chat_session, chat_state)
        return response

    return (
        "Hi 👋 I'm the check-in assistant. "
        "To get started, please send your phone number (e.g. 08012345678)."
    )

def _record_checkin(db: Session, phone: str, service_type: str, connect_name: Optional[str] = None) -> str:
    member = find_member_by_phone(db, phone)
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
                f"{connect._connect_group_prompt()}"
            )

    new = mark_attendance_for_service(
        db,
        member.id,
        service_type,
        connect_name=effective_connect_name,
    )
    if member.first_timer:
        mark_first_timer_event(
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
        existing = get_attendance_for_member_service_today(db, member.id, "connect")
        existing_connect_name = (existing.connect_name or "").strip() if existing else ""
        if existing_connect_name:
            service_label = f"connect ({existing_connect_name})"
        else:
            service_label = "connect"
    return f"👌 You’re already checked in for {service_label} today, {member_display_name}."
