from typing import Optional
from app.services.faq.utils import _load_faq_pairs_from_markdown, _normalize_question_text, _keywords, _fallback_answer_from_markdown, _rerank_by_keyword_overlap, _best_doc_and_score, _extract_answer_from_doc
from app.rag.store import docs_store
from app.common.llm.llm import generate_answer

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
        
        # Pass the top 5 most relevant docs to generate_answer
        top_docs_content = [d.page_content for d in docs[:5]]
        return generate_answer(question, top_docs_content)
    except Exception:
        fallback = _fallback_answer_from_markdown(question)
        if fallback:
            return fallback
        return (
            "I can't access the church knowledge base right now. "
            "Please contact an admin, or try again after embeddings are configured."
        )

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

