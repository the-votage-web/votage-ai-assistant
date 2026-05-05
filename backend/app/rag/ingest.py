from pathlib import Path
import re
from langchain_core.documents import Document
from app.rag.store import docs_store


QA_BLOCK_RE = re.compile(
    r"Q:\s*(?P<question>.+?)\nA:\s*(?P<answer>.+?)(?=\nQ:|\n##\s+Sources|\Z)",
    re.DOTALL,
)


def _parse_qa_docs(text: str) -> list[Document]:
    docs: list[Document] = []
    for match in QA_BLOCK_RE.finditer(text):
        question = match.group("question").strip()
        answer = re.sub(r"\s+", " ", match.group("answer")).strip()
        if not question or not answer:
            continue
        docs.append(
            Document(
                page_content=f"Q: {question}\nA: {answer}",
                metadata={
                    "source": "church_faq.md",
                    "doc_type": "faq_qa",
                    "question": question.lower(),
                },
            )
        )
    return docs


def _clear_existing_source_docs(store, source: str) -> None:
    try:
        existing = store.get(where={"source": source}, include=[])
        ids = existing.get("ids", []) if isinstance(existing, dict) else []
        if ids:
            store.delete(ids=ids)
    except Exception:
        # Fallback for wrappers that don't support nested where operators well.
        try:
            existing = store.get(include=[])
            ids = existing.get("ids", []) if isinstance(existing, dict) else []
            if ids:
                store.delete(ids=ids)
        except Exception:
            pass


def ingest_docs():
    p = Path(__file__).parent / "church_faq.md"
    text = p.read_text(encoding="utf-8")
    docs = _parse_qa_docs(text)
    if not docs:
        raise RuntimeError("No Q/A entries found in church_faq.md.")

    store = docs_store()
    _clear_existing_source_docs(store, "church_faq.md")
    store.add_documents(docs)
    # Newer langchain-chroma persists automatically; older wrappers expose persist().
    if hasattr(store, "persist"):
        store.persist()
    print(f"Ingested {len(docs)} FAQ entries")

if __name__ == "__main__":
    ingest_docs()
