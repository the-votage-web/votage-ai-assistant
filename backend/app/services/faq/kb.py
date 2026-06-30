"""Admin-authored knowledge base: pure helpers + DB CRUD.

Helpers here are import-safe (no DB/network) so they can be unit-tested directly.
DB CRUD functions are added below them and follow the defensive pattern in logs.py.
"""
import re
from typing import List, Dict


def normalize_question(q: str) -> str:
    """Lowercase, collapse whitespace, drop punctuation — for de-dup matching."""
    s = (q or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9\s]", "", s)
    return s


def parse_existing_questions(markdown: str) -> set:
    """Return the normalized set of questions already present as `## Q:` lines."""
    found = set()
    for line in (markdown or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("## Q:"):
            found.add(normalize_question(stripped.replace("## Q:", "", 1)))
    return found


def kb_entry_to_chunk(entry: Dict) -> Dict:
    """Convert a kb_entries row (dict) into the chunk shape the FAQ service uses."""
    eid = str(entry["id"])
    question = entry["question"]
    answer = entry["answer"]
    return {
        "id": f"admin:{eid}",
        "source": entry.get("source", "admin"),
        "question": question,
        "answer": answer,
        "text": f"Q: {question}\nA: {answer}",
    }


def render_faq_markdown(seed_text: str, kb_entries: List[Dict]) -> str:
    """Return a complete faq.md = seed + admin entries, de-duplicated by question.

    The output is always self-contained: callers replace faq.md wholesale.
    """
    existing = parse_existing_questions(seed_text)
    new_lines = []
    for entry in kb_entries:
        key = normalize_question(entry["question"])
        if key in existing:
            continue
        existing.add(key)
        new_lines.append(f"## Q: {entry['question']}")
        new_lines.append(f"A: {entry['answer']}")
        new_lines.append("")
    if not new_lines:
        return seed_text
    return seed_text.rstrip() + "\n\n# Source: admin\n\n" + "\n".join(new_lines).rstrip() + "\n"


import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.db.models import KbEntry

MAX_FIELD_LEN = 4000


def _validate_fields(question: str, answer: str):
    q = (question or "").strip()
    a = (answer or "").strip()
    if not q or not a:
        raise ValueError("Question and answer are both required.")
    if len(q) > MAX_FIELD_LEN or len(a) > MAX_FIELD_LEN:
        raise ValueError(f"Question and answer must each be under {MAX_FIELD_LEN} characters.")
    return q, a


def _entry_to_dict(row: KbEntry) -> Dict:
    return {
        "id": str(row.id),
        "question": row.question,
        "answer": row.answer,
        "source": row.source,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "exported_at": row.exported_at.isoformat() if row.exported_at else None,
    }


def create_kb_entry(db: Session, question: str, answer: str) -> Dict:
    q, a = _validate_fields(question, answer)
    row = KbEntry(id=uuid.uuid4(), question=q, answer=a, source="admin")
    db.add(row)
    db.commit()
    db.refresh(row)
    return _entry_to_dict(row)


def list_kb_entries(db: Session, limit: int = 500) -> List[Dict]:
    rows = db.query(KbEntry).order_by(KbEntry.created_at.desc()).limit(limit).all()
    return [_entry_to_dict(r) for r in rows]


def update_kb_entry(db: Session, entry_id: str, question: str, answer: str):
    q, a = _validate_fields(question, answer)
    row = db.query(KbEntry).filter(KbEntry.id == entry_id).first()
    if not row:
        return None
    row.question = q
    row.answer = a
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _entry_to_dict(row)


def delete_kb_entry(db: Session, entry_id: str) -> bool:
    row = db.query(KbEntry).filter(KbEntry.id == entry_id).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
