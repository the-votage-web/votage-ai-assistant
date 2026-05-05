def _is_successful_checkin_response(text: str) -> bool:
    return text.startswith("✅") or text.startswith("👌")