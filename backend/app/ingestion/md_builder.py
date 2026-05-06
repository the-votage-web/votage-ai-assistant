import re
import json

from openai import OpenAI

from app.db.config import settings


class MarkdownBuilder:
    """
    Splits page content into multiple Q&A pairs per page.
    Uses OpenAI by default, with a deterministic fallback.
    """
    def __init__(self):
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        self._model = settings.OPENAI_CHAT_MODEL

    def build(self, pages: dict):
        all_md = []

        for page, content in pages.items():
            md = self._extract_qa(page, content)
            all_md.append(md)

        return "\n\n".join(all_md)

    def _extract_qa(self, page: str, content: str):
        lines = self._clean_text(content)

        qa_pairs = self._openai_qa_pairs(page, lines)
        if not qa_pairs:
            qa_pairs = self._heuristic_split(lines)
        if page.strip().lower() == "/connect":
            qa_pairs = self._augment_connect_facts(qa_pairs, content)

        md = [f"# Source: {page}\n"]

        for q, a in qa_pairs:
            md.append(f"## Q: {q}\nA: {a}\n")

        return "\n".join(md)

    def _clean_text(self, content: str):
        # remove noise
        content = re.sub(r"\s+", " ", content)
        content = content.replace("\n", " ")

        # split into sentence-like chunks
        sentences = re.split(r"(?<=[.!?])\s+", content)

        return [s.strip() for s in sentences if len(s.strip()) > 5]

    def _augment_connect_facts(self, qa_pairs: list[tuple[str, str]], content: str):
        groups = self._extract_connect_groups(content)
        if not groups:
            return qa_pairs

        count_q = "How many connect groups do we have?"
        list_q = "What are the connect groups available?"
        names = ", ".join(groups)
        count_a = f"We currently have {len(groups)} connect groups in this knowledge base."
        list_a = f"The connect groups available are: {names}."

        # Keep model-generated pairs, then append deterministic facts.
        qa_pairs.append((count_q, count_a))
        qa_pairs.append((list_q, list_a))
        return qa_pairs

    def _extract_connect_groups(self, content: str):
        # Find names directly before the token CONNECT.
        # Examples: KABOD CONNECT, NEWNESS CONNECT, GATEKEEPERS CONNECT.
        candidates = re.findall(
            r"\b([A-Za-z][A-Za-z-]{2,}(?:\s+[A-Za-z][A-Za-z-]{2,}){0,2})\s+CONNECT\b",
            content,
            flags=re.IGNORECASE,
        )
        if not candidates:
            return []

        blacklist = {"join a", "join", "a", "the", "our", "your"}
        normalized = []
        seen = set()
        for raw in candidates:
            name = re.sub(r"\s+", " ", raw).strip()
            lowered = name.lower()
            if lowered in blacklist:
                continue
            # Standardize naming for stable retrieval.
            title_name = " ".join(part.capitalize() for part in name.split())
            if title_name.lower() in seen:
                continue
            seen.add(title_name.lower())
            normalized.append(f"{title_name} CONNECT")
        return normalized

    def _openai_qa_pairs(self, page: str, lines: list[str]):
        if not self._client or not lines:
            return []

        # Keep prompt size bounded for predictable ingestion cost/latency.
        sample = "\n".join(lines[:120])
        prompt = (
            "Create concise FAQ pairs from the page text below.\n"
            "Return ONLY valid JSON in this exact shape:\n"
            "{\"pairs\":[{\"question\":\"...\",\"answer\":\"...\"}]}\n"
            "Rules:\n"
            "- 4 to 8 pairs\n"
            "- Questions must be user-facing and specific\n"
            "- Answers must be faithful to source text\n"
            "- No markdown, no extra keys, no commentary\n\n"
            f"Page: {page}\n"
            f"Text:\n{sample}"
        )

        try:
            response = self._client.responses.create(
                model=self._model,
                input=prompt,
                max_output_tokens=800,
                temperature=0.2,
            )
            raw = (response.output_text or "").strip()
            data = json.loads(raw)
            pairs = data.get("pairs", [])
            normalized = []
            for item in pairs:
                q = str(item.get("question", "")).strip()
                a = str(item.get("answer", "")).strip()
                if q and a:
                    normalized.append((q, a))
            return normalized
        except Exception as exc:
            print(f"OpenAI Q&A build failed for {page}: {exc!r}")
            return []

    def _heuristic_split(self, lines: list):
        """
        Converts messy page text → multiple Q/A pairs
        """

        qa_pairs = []

        buffer = []

        for line in lines:
            buffer.append(line)

            # trigger split when chunk is big enough
            if len(buffer) >= 3:

                text = " ".join(buffer)

                q = self._guess_question(text)
                a = self._guess_answer(text)

                if q and a:
                    qa_pairs.append((q, a))

                buffer = []

        # leftover
        if buffer:
            text = " ".join(buffer)
            q = self._guess_question(text)
            a = self._guess_answer(text)

            if q and a:
                qa_pairs.append((q, a))

        return qa_pairs

    def _guess_question(self, text: str):
        """
        Extract likely question
        """

        patterns = [
            "what is",
            "where is",
            "how to",
            "what are",
            "why",
            "when"
        ]

        lower = text.lower()

        for p in patterns:
            if p in lower:
                return text[:120] + "?"

        return None

    def _guess_answer(self, text: str):
        """
        Clean answer extraction
        """

        return text.strip()[:300]
