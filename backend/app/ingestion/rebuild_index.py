r"""Rebuild the vector store from faq.md.

`faq.md` is the single source of truth for the chatbot's knowledge. After you
edit it (fix an answer, update the address) or add new content (e.g. document
imports), run this to re-sync the meaning-search vector store:

    cd backend
    .\.venv\Scripts\python.exe -m app.ingestion.rebuild_index

It clears the faq_embeddings table and re-embeds every Q&A in faq.md, so the
vector store always matches the file (no stale answers, no duplicates).

NOTE: also restart the backend afterwards, so the keyword-search side and the
in-memory answer cache reload the new faq.md.
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv
load_dotenv()

from pathlib import Path
import psycopg2

from app.db.config import settings
from app.services.faq.faq import faq_service


def main() -> None:
    md_path = Path(__file__).resolve().parents[1] / "data" / "faq.md"
    md = md_path.read_text(encoding="utf-8")
    print(f"Read {md_path} ({len(md)} chars)")

    # 1. Clear the existing vector store so we don't accumulate duplicates.
    conn = psycopg2.connect(settings.DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM faq_embeddings;")
        conn.commit()
        print("Cleared faq_embeddings.")
    finally:
        conn.close()

    # 2. Re-embed everything currently in faq.md.
    count = faq_service.build_index(md)
    print(f"Re-embedded {count} Q&A pairs from faq.md.")
    print("Done. Restart the backend so keyword search + cache pick up the changes.")


if __name__ == "__main__":
    main()
