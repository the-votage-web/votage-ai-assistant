import re
import time
from pathlib import Path
from collections import OrderedDict
from difflib import SequenceMatcher

from app.db.config import settings
from app.rag.chunker import QnAChunker
from app.rag.embedder import OpenAIEmbedder
from app.rag.retriever import PgVectorRetriever
from app.rag.generator import OpenAIGenerator
from app.services.faq.logs import log_chat
from app.services.faq.kb import kb_entry_to_chunk

# Shown when the bot should defer to a human: church-specific facts it doesn't have,
# and personal/pastoral questions. (The model emits a sentinel; see ask_with_meta.)
NO_ANSWER_REPLY = "Sorry, I don't have that information yet. Kindly reach out to the church admin for help."


class FAQTemporarilyUnavailableError(Exception):
    pass


class FAQService:
    def __init__(self):
        self.chunker = QnAChunker()
        self.embedder = OpenAIEmbedder()
        self.retriever = PgVectorRetriever(settings.DATABASE_URL)
        self.generator = OpenAIGenerator()
        self._faq_chunks = self._load_faq_chunks() + self._load_kb_chunks()
        self._kb_vocab = self._build_vocab(self._faq_chunks)
        self._answer_cache = OrderedDict()
        self._cache_ttl_seconds = 900
        self._cache_max_entries = 300

    def build_index(self, markdown_text: str):
        chunks = self.chunker.parse(markdown_text)

        embedded = self.embedder.embed_batch(chunks)

        self.retriever.store_vectors(embedded)

        return len(embedded)

    def ask(self, question: str) -> str:
        return self.ask_with_meta(question)["answer"]

    def ask_with_meta(self, question: str) -> dict:
        """Answer a question, returning {answer, answered, top_score}.

        answered=False means nothing in the knowledge base was relevant, so the
        bot gave the honest "I don't have that information" reply (a gap to fill).
        """
        cache_key = self._cache_key(question)
        cached = self._cache_get(cache_key)
        if cached:
            return {"answer": cached, "answered": True, "top_score": None}

        use_wide_context = self._is_count_or_listing_query(question)
        try:
            query_vector = self.embedder.embed(question)
            vector_context = self.retriever.search(query_vector, top_k=10 if use_wide_context else 6)
            top_score = max((c.get("score", 0.0) for c in vector_context), default=0.0)
            lexical_context = self._search_markdown(question, top_k=12 if use_wide_context else 6)
            # Give the model the WHOLE knowledge base (it's small) so it can reason about
            # the church holistically — most-relevant entries first, then everything else.
            relevant = self._merge_contexts(question, vector_context, lexical_context, top_k=12 if use_wide_context else 7)
            seen = {(c.get("question"), c.get("answer")) for c in relevant}
            context = relevant + [c for c in self._faq_chunks if (c.get("question"), c.get("answer")) not in seen]
            answer = self.generator.generate(question, context)

            # The model chose to defer (a church-specific fact it doesn't have, or a
            # personal/pastoral question) -> show the friendly "reach out to admin" reply.
            if self._is_low_information_answer(answer):
                return {"answer": NO_ANSWER_REPLY, "answered": False, "top_score": top_score}

            self._cache_set(cache_key, answer)
            return {"answer": answer, "answered": True, "top_score": top_score}
        except Exception as exc:
            print(f"FAQ primary path failed, using fallback: {exc!r}")
            lexical_context = self._search_markdown(question, top_k=12 if use_wide_context else 7)
            if lexical_context:
                try:
                    answer = self.generator.generate(question, lexical_context)
                    if not self._is_low_information_answer(answer):
                        self._cache_set(cache_key, answer)
                        return {"answer": answer, "answered": True, "top_score": None}
                except Exception:
                    pass
            # Couldn't produce an answer (e.g. a transient backend error) — reply
            # honestly rather than surfacing a scary error to the visitor.
            return {"answer": NO_ANSWER_REPLY, "answered": False, "top_score": None}

    def _cache_key(self, question: str):
        normalized = question.lower().strip()
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
        return normalized

    def _cache_get(self, key: str):
        item = self._answer_cache.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at < time.time():
            self._answer_cache.pop(key, None)
            return None
        self._answer_cache.move_to_end(key)
        return value

    def _cache_set(self, key: str, value: str):
        if self._is_low_information_answer(value):
            return
        self._answer_cache[key] = (time.time() + self._cache_ttl_seconds, value)
        self._answer_cache.move_to_end(key)
        if len(self._answer_cache) > self._cache_max_entries:
            self._answer_cache.popitem(last=False)

    def _is_low_information_answer(self, answer: str):
        if not answer:
            return True
        a = answer.lower().strip()
        markers = [
            "i don't have enough information",
            "i do not have enough information",
            "i don't know",
            "not enough information",
        ]
        return any(m in a for m in markers)

    def _load_faq_chunks(self):
        faq_path = Path(__file__).resolve().parents[2] / "data" / "faq.md"
        if not faq_path.exists():
            return []
        markdown_text = faq_path.read_text(encoding="utf-8")
        lines = markdown_text.splitlines()
        chunks = []
        current_source = "unknown"
        current_q = None
        current_a = []

        def flush():
            nonlocal current_q, current_a
            if not current_q or not current_a:
                return
            answer = " ".join(current_a).strip()
            chunks.append({
                "id": f"{current_source}:{len(chunks)}",
                "source": current_source,
                "question": current_q,
                "answer": answer,
                "text": f"Q: {current_q}\nA: {answer}",
            })
            current_q = None
            current_a = []

        for raw_line in lines:
            line = raw_line.strip()
            if line.startswith("# Source:"):
                flush()
                current_source = line.replace("# Source:", "").strip()
                continue
            if line.startswith("## Q:"):
                flush()
                current_q = line.replace("## Q:", "").strip()
                continue
            if line.startswith("A:"):
                current_a.append(line.replace("A:", "").strip())
                continue
            if current_q and line:
                current_a.append(line)
        flush()
        return chunks

    def read_seed_markdown(self) -> str:
        faq_path = Path(__file__).resolve().parents[2] / "data" / "faq.md"
        return faq_path.read_text(encoding="utf-8") if faq_path.exists() else ""

    def _load_kb_chunks(self):
        """Load admin-authored entries from the DB. Defensive — never blocks startup."""
        try:
            from app.db.session import SessionLocal
            from app.services.faq.kb import list_kb_entries
            db = SessionLocal()
            try:
                entries = list_kb_entries(db)
            finally:
                db.close()
            return [kb_entry_to_chunk(e) for e in entries]
        except Exception as exc:
            print(f"kb chunk load failed: {exc!r}")
            return []

    def add_entry(self, entry: dict):
        """Embed + upsert a KB entry and add it to the live in-memory chunks."""
        chunk = kb_entry_to_chunk(entry)
        vector = self.embedder.embed(chunk["text"])
        self.retriever.upsert_vector({**chunk, "embedding": vector, "metadata": {"source": chunk["source"]}})
        self._faq_chunks = [c for c in self._faq_chunks if c["id"] != chunk["id"]]
        self._faq_chunks.append(chunk)
        self._kb_vocab = self._build_vocab(self._faq_chunks)

    def update_entry(self, entry: dict):
        """Re-embed and replace an existing KB entry (same id)."""
        self.add_entry(entry)

    def remove_entry(self, entry_id: str):
        """Delete a KB entry's vector and live chunk."""
        vector_id = f"admin:{entry_id}"
        self.retriever.delete_vector(vector_id)
        self._faq_chunks = [c for c in self._faq_chunks if c["id"] != vector_id]
        self._kb_vocab = self._build_vocab(self._faq_chunks)

    def _tokens(self, text: str):
        words = re.findall(r"[a-zA-Z0-9']+", text.lower())
        return {self._normalize_token(w) for w in words if len(w) > 2}

    def _normalize_token(self, token: str):
        t = token.lower().strip()
        if len(t) > 4 and t.endswith("ies"):
            return t[:-3] + "y"
        if len(t) > 3 and t.endswith("s"):
            return t[:-1]
        return t

    def _build_vocab(self, chunks):
        vocab = set()
        for chunk in chunks:
            vocab.update(self._tokens(chunk["question"]))
            vocab.update(self._tokens(chunk["answer"]))
            source_name = str(chunk.get("source", "")).replace("/", " ")
            vocab.update(self._tokens(source_name))
        return vocab

    def _expand_query_tokens(self, tokens):
        expanded = set(tokens)
        for token in tokens:
            if len(token) < 4:
                continue
            best_match = None
            best_ratio = 0.0
            for candidate in self._kb_vocab:
                ratio = SequenceMatcher(None, token, candidate).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = candidate
            if best_match and best_ratio >= 0.8:
                expanded.add(best_match)
        return expanded

    def _is_count_or_listing_query(self, question: str):
        q = question.lower()
        return any(k in q for k in ["how many", "count", "total", "list", "all of"])

    def _source_hint_bonus(self, question: str, chunk: dict):
        q = question.lower()
        source = str(chunk.get("source", "")).lower()
        bonus = 0
        if "connect" in q and "/connect" in source:
            bonus += 4
        if "service" in q and "/home" in source:
            bonus += 2
        if "pastor" in q and "/about" in source:
            bonus += 2
        if "sermon" in q and "/sermons" in source:
            bonus += 2
        return bonus

    def _search_markdown(self, question: str, top_k: int = 7):
        if not self._faq_chunks:
            return []
        query_tokens = self._expand_query_tokens(self._tokens(question))
        query_text = question.lower()
        if query_text.startswith("what about "):
            query_tokens = query_tokens.union(
                self._expand_query_tokens(self._tokens(query_text.replace("what about ", "", 1)))
            )
        scored = []
        for chunk in self._faq_chunks:
            chunk_tokens = self._tokens(chunk["question"]) | self._tokens(chunk["answer"])
            overlap = len(query_tokens.intersection(chunk_tokens))
            score = overlap + self._source_hint_bonus(question, chunk)
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored[:top_k]]

    def _merge_contexts(self, question: str, vector_context, lexical_context, top_k: int = 7):
        merged = []
        seen = set()
        for chunk in lexical_context + vector_context:
            key = (chunk.get("question"), chunk.get("answer"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(chunk)
        if not merged:
            return []
        merged.sort(
            key=lambda c: (
                len(self._tokens(question).intersection(self._tokens(c.get("question", "")) | self._tokens(c.get("answer", ""))))
                + self._source_hint_bonus(question, c)
            ),
            reverse=True,
        )
        return merged[:top_k]

    def _fallback_from_markdown(self, question: str):
        question_tokens = self._expand_query_tokens(self._tokens(question))
        if not self._faq_chunks:
            return None
        if not question_tokens:
            return self._faq_chunks[0]["answer"]

        best_answer = None
        best_score = 0
        for chunk in self._faq_chunks:
            candidate_tokens = self._tokens(chunk["question"]) | self._tokens(chunk["answer"])
            score = len(question_tokens.intersection(candidate_tokens)) + self._source_hint_bonus(question, chunk)
            if score > best_score:
                best_score = score
                best_answer = chunk["answer"]

        if best_answer:
            return best_answer
        return self._faq_chunks[0]["answer"]

faq_service = FAQService()


def handle_faq(db, session_id: str, message: str):
    """Main chatbot entry point: answer the question and log it for review."""
    result = faq_service.ask_with_meta(message)
    answer = result["answer"]

    # Record every question (and whether it was answered) so the team can see
    # how the bot is doing and which questions need answers added.
    log_chat(
        db,
        session_id=session_id,
        question=message,
        answer=answer,
        answered=result["answered"],
        top_score=result.get("top_score"),
    )
    return answer
