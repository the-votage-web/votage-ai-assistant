import json
from sqlalchemy.orm import Session

def _load_state(raw_state: str) -> dict:
    try:
        data = json.loads(raw_state or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _save_state(db: Session, chat_session, state: dict) -> None:
    chat_session.state_json = json.dumps(state)
    db.commit()
