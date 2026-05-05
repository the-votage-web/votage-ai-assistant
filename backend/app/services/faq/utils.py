from typing import Optional
import re
from pathlib import Path
from app.constants.faq import FAQ_BLOCK_RE, STOPWORDS, GREETING_TOKENS

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

def _normalize_question_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()

def _keywords(text: str) -> set[str]:
    raw = re.findall(r"[a-zA-Z0-9']+", text.lower())
    return {
        _normalize_token(t)
        for t in raw
        if len(t) > 2 and _normalize_token(t) not in STOPWORDS
    }

def _normalize_token(token: str) -> str:
    t = token.lower().strip()
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("s"):
        return t[:-1]
    return t

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


def _is_greeting_message(message: str) -> bool:
    normalized = re.sub(r"\s+", " ", message.lower()).strip()
    return normalized in GREETING_TOKENS


