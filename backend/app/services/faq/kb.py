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
