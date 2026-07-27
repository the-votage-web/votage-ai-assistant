# Admin Chat-History & Knowledge Review — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a private admin page where the church tech team can review all chatbot questions/answers, filter by answered/unanswered, author answers for gaps directly into the knowledge base (used live, no restart), and export an up-to-date `faq.md` for git.

**Architecture:** Admin answers are stored in a new `kb_entries` table in the shared Neon database and embedded into the existing `faq_embeddings` pgvector table — never written to `faq.md` directly (a deploy would overwrite it). The running `FAQService` loads `kb_entries` alongside `faq.md` and exposes live add/update/remove. A new admin-gated FastAPI router serves login, logs, KB CRUD, and a full-`faq.md` export. The frontend adds an `/admin` route gated by the existing shared `ADMIN_API_KEY` (sent as the `X-Admin-Key` header).

**Tech Stack:** FastAPI + SQLAlchemy + psycopg2 (backend), Postgres/pgvector on Neon, OpenAI embeddings (`text-embedding-3-small`), Next.js App Router + React + TypeScript (frontend).

## Global Constraints

- Backend schema is created by raw SQL in `app/rag/db_init.py` (`CREATE TABLE IF NOT EXISTS`), run at startup — NOT by Alembic. New tables/columns go there to match the existing `chat_logs`/`faq_embeddings` pattern.
- Admin endpoints MUST be gated by the existing `require_admin` dependency (checks `X-Admin-Key` against `settings.ADMIN_API_KEY`, deny-by-default when unset).
- The admin secret is the existing `ADMIN_API_KEY` setting (single shared password). Do NOT introduce a new secret or per-user accounts.
- KB-entry vector ids are deterministic: `f"admin:{kb_entry_id}"`. Use this exact format everywhere so edit/delete can target the vector.
- All write/log paths must be defensive: an embedding/DB failure must never crash the request or the page (follow the existing `try/except` + `rollback` pattern in `app/services/faq/logs.py`).
- Embeddings use the existing `OpenAIEmbedder`; vector writes use `PgVectorRetriever`. The pgvector column is `vector(1536)`.
- Frontend stores the password in `sessionStorage` (not `localStorage`) and attaches it as the `X-Admin-Key` header. A `403` forces return to the login view.
- Windows console: keep `PYTHONUTF8=1` when running the backend (existing project gotcha).
- Tests requiring DB/OpenAI assume the local env is configured (`.env` present, Neon reachable with VPN off). Pure-logic tests must run with no network.

---

## File Structure

**Backend**
- Modify `app/db/models.py` — add `KbEntry` model; add `resolved_at` to `ChatLog`.
- Modify `app/rag/db_init.py` — `CREATE TABLE IF NOT EXISTS kb_entries`; `ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS resolved_at`.
- Create `app/services/faq/kb.py` — pure helpers (`normalize_question`, `parse_existing_questions`, `kb_entry_to_chunk`, `render_faq_markdown`) + DB CRUD (`create_kb_entry`, `list_kb_entries`, `update_kb_entry`, `delete_kb_entry`).
- Modify `app/services/faq/logs.py` — extend `get_logs` (status + keyword + `resolved_at`); add `mark_resolved`.
- Modify `app/rag/retriever.py` — add `upsert_vector` and `delete_vector`.
- Modify `app/services/faq/faq.py` — load KB chunks at init; add `add_entry`/`update_entry`/`remove_entry`; expose `read_seed_markdown`.
- Create `app/api/admin.py` — admin router (login, logs, KB CRUD, export).
- Modify `app/main.py` — include `admin_router`.

**Backend tests**
- Create `backend/tests/test_kb_helpers.py` — pure-logic tests (no network).
- Create `backend/tests/test_admin_api.py` — TestClient tests with `dependency_overrides` + monkeypatch.

**Frontend**
- Create `frontend/app/admin/page.tsx` — login + dashboard + editor + KB tab + export + sign out.
- Create `frontend/app/admin/admin.module.css` — styling (mirror `app/register/register.module.css` patterns).

**Docs**
- Modify `CHANGE_LOG.md` — document the feature.

---

## Task 1: Database schema (model + startup DDL)

**Files:**
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/rag/db_init.py`

**Interfaces:**
- Produces: `KbEntry` ORM model (`id: UUID`, `question: str`, `answer: str`, `source: str`, `created_at`, `updated_at`, `exported_at`); `ChatLog.resolved_at` column; runtime tables `kb_entries` and `chat_logs.resolved_at`.

- [ ] **Step 1: Add the `KbEntry` model and `resolved_at` column**

In `backend/app/db/models.py`, add `resolved_at` to `ChatLog` (after `created_at`):

```python
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

Then add this new model at the end of the file:

```python
class KbEntry(Base):
    """Admin-authored knowledge. Stored in the DB (not faq.md) so it survives
    deploys and is used by the bot live. Mirrored into faq_embeddings for search."""
    __tablename__ = "kb_entries"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="admin")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    exported_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 2: Add startup DDL in `db_init.py`**

In `backend/app/rag/db_init.py`, inside `setup()` after the `chat_logs` `CREATE TABLE` block and before `self.conn.commit()`, add:

```python
            # Admin-authored knowledge base entries (used live + exported to faq.md)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kb_entries (
                    id UUID PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'admin',
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ,
                    exported_at TIMESTAMPTZ
                );
            """)

            # "Mark resolved" support on existing chat_logs
            cur.execute("""
                ALTER TABLE chat_logs
                ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ;
            """)
```

- [ ] **Step 3: Verify the model imports and exposes the new columns**

Run: `cd backend && python -c "from app.db.models import KbEntry, ChatLog; print('resolved_at' in ChatLog.__table__.columns, 'question' in KbEntry.__table__.columns)"`
Expected: `True True`

- [ ] **Step 4: Verify startup creates the schema (manual, DB reachable)**

Run: `cd backend && python -c "from app.db.config import settings; from app.rag.db_init import DBInitializer; DBInitializer(settings.DATABASE_URL).setup()"`
Expected: prints `✅ pgvector DB initialized` with no error (idempotent — safe to re-run).

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/models.py backend/app/rag/db_init.py
git commit -m "feat(admin): add kb_entries table and chat_logs.resolved_at"
```

---

## Task 2: KB pure helpers (normalize, parse, chunk, export render)

**Files:**
- Create: `backend/app/services/faq/kb.py`
- Test: `backend/tests/test_kb_helpers.py`

**Interfaces:**
- Produces:
  - `normalize_question(q: str) -> str`
  - `parse_existing_questions(markdown: str) -> set[str]` (normalized `## Q:` lines)
  - `kb_entry_to_chunk(entry: dict) -> dict` (keys: `id`,`source`,`question`,`answer`,`text`; `id` = `f"admin:{entry['id']}"`)
  - `render_faq_markdown(seed_text: str, kb_entries: list[dict]) -> str`
- Consumes: nothing (pure module; DB CRUD added in Task 5 in the same file).

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_kb_helpers.py`:

```python
import unittest
from app.services.faq.kb import (
    normalize_question,
    parse_existing_questions,
    kb_entry_to_chunk,
    render_faq_markdown,
)


class TestKbHelpers(unittest.TestCase):
    def test_normalize_question_is_case_and_space_insensitive(self):
        self.assertEqual(
            normalize_question("  What  TIME is service? "),
            normalize_question("what time is service"),
        )

    def test_parse_existing_questions_reads_q_lines(self):
        md = "# Source: home\n## Q: What time is service?\nA: 9am\n## Q: Where are you?\nA: Benin"
        found = parse_existing_questions(md)
        self.assertIn(normalize_question("What time is service?"), found)
        self.assertIn(normalize_question("Where are you?"), found)

    def test_kb_entry_to_chunk_shape_and_id(self):
        chunk = kb_entry_to_chunk({"id": "abc-123", "question": "Q1", "answer": "A1"})
        self.assertEqual(chunk["id"], "admin:abc-123")
        self.assertEqual(chunk["question"], "Q1")
        self.assertEqual(chunk["answer"], "A1")
        self.assertEqual(chunk["text"], "Q: Q1\nA: A1")
        self.assertEqual(chunk["source"], "admin")

    def test_render_appends_new_entries_under_admin_source(self):
        seed = "# Source: home\n## Q: What time is service?\nA: 9am"
        out = render_faq_markdown(seed, [{"id": "1", "question": "Do you allow pets?", "answer": "Service animals welcome."}])
        self.assertIn("# Source: admin", out)
        self.assertIn("## Q: Do you allow pets?", out)
        self.assertIn("A: Service animals welcome.", out)
        self.assertTrue(out.startswith(seed.rstrip()))

    def test_render_dedups_questions_already_in_seed(self):
        seed = "# Source: home\n## Q: What time is service?\nA: 9am"
        out = render_faq_markdown(seed, [{"id": "1", "question": "what TIME is service?", "answer": "different"}])
        self.assertEqual(out.count("## Q: "), 1)  # no duplicate question added
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_kb_helpers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.faq.kb'`

- [ ] **Step 3: Implement the helpers**

Create `backend/app/services/faq/kb.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_kb_helpers.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/faq/kb.py backend/tests/test_kb_helpers.py
git commit -m "feat(admin): KB pure helpers (normalize, parse, chunk, export render)"
```

---

## Task 3: Vector upsert + delete on the retriever

**Files:**
- Modify: `backend/app/rag/retriever.py`

**Interfaces:**
- Consumes: existing `_ensure_conn`, `_to_vector_literal`.
- Produces:
  - `upsert_vector(chunk: dict) -> None` — chunk has `id`,`question`,`answer`,`text`,`embedding`,`metadata?`
  - `delete_vector(vector_id: str) -> None`

- [ ] **Step 1: Implement `upsert_vector` and `delete_vector`**

In `backend/app/rag/retriever.py`, add these methods to `PgVectorRetriever` (after `store_vectors`):

```python
    def upsert_vector(self, chunk: Dict):
        """Insert or replace a single vector row (used for live admin KB edits)."""
        try:
            self._ensure_conn()
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO faq_embeddings (id, question, answer, text, embedding, metadata)
                    VALUES (%s, %s, %s, %s, %s::vector, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        question = EXCLUDED.question,
                        answer = EXCLUDED.answer,
                        text = EXCLUDED.text,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata
                    """,
                    (
                        chunk["id"],
                        chunk["question"],
                        chunk["answer"],
                        chunk["text"],
                        self._to_vector_literal(chunk["embedding"]),
                        json.dumps(chunk.get("metadata", {})),
                    ),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def delete_vector(self, vector_id: str):
        """Remove a single vector row by id (used when an admin deletes a KB entry)."""
        try:
            self._ensure_conn()
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM faq_embeddings WHERE id = %s", (vector_id,))
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
```

- [ ] **Step 2: Verify it imports and the methods exist**

Run: `cd backend && python -c "from app.rag.retriever import PgVectorRetriever; print(hasattr(PgVectorRetriever, 'upsert_vector'), hasattr(PgVectorRetriever, 'delete_vector'))"`
Expected: `True True`

- [ ] **Step 3: Commit**

```bash
git add backend/app/rag/retriever.py
git commit -m "feat(admin): pgvector upsert_vector and delete_vector for live KB edits"
```

---

## Task 4: FAQService live KB integration

**Files:**
- Modify: `backend/app/services/faq/faq.py`
- Test: `backend/tests/test_admin_api.py` (FAQService section; file created here, extended in Task 6)

**Interfaces:**
- Consumes: `kb_entry_to_chunk` (Task 2), `upsert_vector`/`delete_vector` (Task 3), `list_kb_entries` (Task 5 — guard import so load is defensive).
- Produces on `faq_service`:
  - `add_entry(entry: dict) -> None` (entry: `id`,`question`,`answer`,`source?`)
  - `update_entry(entry: dict) -> None`
  - `remove_entry(entry_id: str) -> None`
  - `read_seed_markdown() -> str`

- [ ] **Step 1: Add KB loading + live mutation methods**

In `backend/app/services/faq/faq.py`, add the import near the top:

```python
from app.services.faq.kb import kb_entry_to_chunk
```

In `FAQService.__init__`, change the chunk-loading line:

```python
        self._faq_chunks = self._load_faq_chunks() + self._load_kb_chunks()
```

Add these methods to `FAQService` (after `_load_faq_chunks`):

```python
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
```

- [ ] **Step 2: Write a failing test for in-memory mutation (mocked services)**

Create `backend/tests/test_admin_api.py` with this first test (more added in Task 6):

```python
import unittest
from unittest.mock import MagicMock


class TestFaqServiceLiveEdits(unittest.TestCase):
    def _service(self):
        from app.services.faq.faq import faq_service
        faq_service.embedder = MagicMock()
        faq_service.embedder.embed.return_value = [0.0] * 1536
        faq_service.retriever = MagicMock()
        return faq_service

    def test_add_entry_appends_live_chunk(self):
        svc = self._service()
        before = len(svc._faq_chunks)
        svc.add_entry({"id": "test-xyz", "question": "Test only Q?", "answer": "Test only A."})
        ids = [c["id"] for c in svc._faq_chunks]
        self.assertIn("admin:test-xyz", ids)
        svc.retriever.upsert_vector.assert_called_once()
        # cleanup so the singleton isn't polluted for other tests
        svc.remove_entry("test-xyz")
        self.assertEqual(len(svc._faq_chunks), before)
```

- [ ] **Step 3: Run the test**

Run: `cd backend && python -m pytest tests/test_admin_api.py::TestFaqServiceLiveEdits -v`
Expected: PASS. (Note: importing `faq_service` constructs the singleton, which connects to the DB — run with `.env` configured and Neon reachable.)

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/faq/faq.py backend/tests/test_admin_api.py
git commit -m "feat(admin): FAQService loads KB entries and supports live add/update/remove"
```

---

## Task 5: KB DB CRUD + logs filtering/resolve

**Files:**
- Modify: `backend/app/services/faq/kb.py`
- Modify: `backend/app/services/faq/logs.py`

**Interfaces:**
- Produces in `kb.py`:
  - `create_kb_entry(db, question, answer) -> dict` (raises `ValueError` on empty/too-long)
  - `list_kb_entries(db, limit=500) -> list[dict]`
  - `update_kb_entry(db, entry_id, question, answer) -> dict | None`
  - `delete_kb_entry(db, entry_id) -> bool`
  - `MAX_FIELD_LEN = 4000`
- Produces in `logs.py`:
  - `get_logs(db, status="all", q=None, limit=100) -> list[dict]` (now includes `resolved_at`)
  - `mark_resolved(db, log_id) -> None`
- Consumes: `KbEntry`, `ChatLog` models; `normalize_question` (validation reuse).

- [ ] **Step 1: Add validation tests for `create_kb_entry`**

Append to `backend/tests/test_kb_helpers.py`:

```python
from app.services.faq.kb import _validate_fields, MAX_FIELD_LEN  # noqa: E402


class TestKbValidation(unittest.TestCase):
    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            _validate_fields("  ", "answer")
        with self.assertRaises(ValueError):
            _validate_fields("question", "")

    def test_rejects_too_long(self):
        with self.assertRaises(ValueError):
            _validate_fields("q", "a" * (MAX_FIELD_LEN + 1))

    def test_accepts_and_strips(self):
        q, a = _validate_fields("  hi  ", "  there  ")
        self.assertEqual((q, a), ("hi", "there"))
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && python -m pytest tests/test_kb_helpers.py::TestKbValidation -v`
Expected: FAIL — `ImportError: cannot import name '_validate_fields'`

- [ ] **Step 3: Add CRUD + validation to `kb.py`**

Append to `backend/app/services/faq/kb.py`:

```python
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
```

- [ ] **Step 4: Run validation tests to verify pass**

Run: `cd backend && python -m pytest tests/test_kb_helpers.py -v`
Expected: PASS (all helper + validation tests)

- [ ] **Step 5: Extend `logs.py` with status/keyword filter + `mark_resolved`**

Replace the body of `get_logs` in `backend/app/services/faq/logs.py` and add `mark_resolved`:

```python
from datetime import datetime, timezone


def get_logs(db: Session, status: str = "all", q: Optional[str] = None, limit: int = 100):
    """Return recent chat logs (newest first) as plain dicts.

    status: "all" | "answered" | "unanswered". q: optional keyword (case-insensitive)
    matched against the question text.
    """
    query = db.query(ChatLog)
    if status == "unanswered":
        query = query.filter(ChatLog.answered.is_(False))
    elif status == "answered":
        query = query.filter(ChatLog.answered.is_(True))
    if q:
        query = query.filter(ChatLog.question.ilike(f"%{q}%"))
    rows = query.order_by(ChatLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": str(r.id),
            "session_id": r.session_id,
            "question": r.question,
            "answer": r.answer,
            "answered": r.answered,
            "top_score": r.top_score,
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def mark_resolved(db: Session, log_id: str) -> None:
    """Stamp a chat log as resolved (an admin answered this gap). Never raises."""
    try:
        row = db.query(ChatLog).filter(ChatLog.id == log_id).first()
        if row:
            row.resolved_at = datetime.now(timezone.utc)
            db.commit()
    except Exception as exc:
        db.rollback()
        print(f"mark_resolved failed: {exc!r}")
```

Keep the existing `log_chat` function unchanged.

- [ ] **Step 6: Verify imports**

Run: `cd backend && python -c "from app.services.faq.kb import create_kb_entry, list_kb_entries, update_kb_entry, delete_kb_entry; from app.services.faq.logs import get_logs, mark_resolved; print('ok')"`
Expected: `ok`

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/faq/kb.py backend/app/services/faq/logs.py backend/tests/test_kb_helpers.py
git commit -m "feat(admin): KB CRUD + chat-log status/keyword filter and mark_resolved"
```

---

## Task 6: Admin API router + wiring

**Files:**
- Create: `backend/app/api/admin.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_admin_api.py` (extend)

**Interfaces:**
- Consumes: `require_admin` (move/import from `app/api/chat.py`), `get_db`, `get_logs`/`mark_resolved`, kb CRUD, `faq_service`, `render_faq_markdown`, `read_seed_markdown`.
- Produces routes (mounted under `/api`): `POST /admin/login`, `GET /admin/logs`, `POST /admin/kb`, `GET /admin/kb`, `PUT /admin/kb/{id}`, `DELETE /admin/kb/{id}`, `GET /admin/kb/export`.

- [ ] **Step 1: Write the admin router**

Create `backend/app/api/admin.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.config import settings
from app.services.faq.logs import get_logs, mark_resolved
from app.services.faq.kb import (
    create_kb_entry, list_kb_entries, update_kb_entry, delete_kb_entry,
    render_faq_markdown,
)
from app.services.faq.faq import faq_service

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_admin(x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    expected = settings.ADMIN_API_KEY
    if not expected or x_admin_key != expected:
        raise HTTPException(status_code=403, detail="Admin access required.")


class LoginIn(BaseModel):
    password: str


class KbIn(BaseModel):
    question: str
    answer: str
    from_log_id: Optional[str] = None


@router.post("/admin/login")
def admin_login(payload: LoginIn):
    if not settings.ADMIN_API_KEY or payload.password != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid password.")
    return {"ok": True}


@router.get("/admin/logs")
def admin_logs(status: str = "all", q: Optional[str] = None, limit: int = 100,
               db: Session = Depends(get_db), _admin: None = Depends(require_admin)):
    limit = max(1, min(limit, 500))
    return get_logs(db, status=status, q=q, limit=limit)


@router.get("/admin/kb")
def admin_kb_list(db: Session = Depends(get_db), _admin: None = Depends(require_admin)):
    return list_kb_entries(db)


@router.post("/admin/kb")
def admin_kb_create(payload: KbIn, db: Session = Depends(get_db), _admin: None = Depends(require_admin)):
    try:
        entry = create_kb_entry(db, payload.question, payload.answer)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        faq_service.add_entry(entry)
    except Exception as exc:
        print(f"admin_kb_create: live index update failed (entry saved): {exc!r}")
    if payload.from_log_id:
        mark_resolved(db, payload.from_log_id)
    return entry


@router.put("/admin/kb/{entry_id}")
def admin_kb_update(entry_id: str, payload: KbIn, db: Session = Depends(get_db), _admin: None = Depends(require_admin)):
    try:
        entry = update_kb_entry(db, entry_id, payload.question, payload.answer)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found.")
    try:
        faq_service.update_entry(entry)
    except Exception as exc:
        print(f"admin_kb_update: live index update failed (entry saved): {exc!r}")
    return entry


@router.delete("/admin/kb/{entry_id}")
def admin_kb_delete(entry_id: str, db: Session = Depends(get_db), _admin: None = Depends(require_admin)):
    ok = delete_kb_entry(db, entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Entry not found.")
    try:
        faq_service.remove_entry(entry_id)
    except Exception as exc:
        print(f"admin_kb_delete: live index update failed (row deleted): {exc!r}")
    return {"ok": True}


@router.get("/admin/kb/export")
def admin_kb_export(db: Session = Depends(get_db), _admin: None = Depends(require_admin)):
    seed = faq_service.read_seed_markdown()
    entries = list_kb_entries(db)
    content = render_faq_markdown(seed, entries)
    return PlainTextResponse(
        content,
        headers={"Content-Disposition": 'attachment; filename="faq.md"'},
        media_type="text/markdown",
    )
```

- [ ] **Step 2: Wire the router in `main.py`**

In `backend/app/main.py`, add the import with the other routers:

```python
from app.api.admin import router as admin_router
```

And register it after the existing `include_router` calls:

```python
app.include_router(admin_router, prefix="/api")
```

- [ ] **Step 3: Add auth-gate tests (TestClient)**

Append to `backend/tests/test_admin_api.py`:

```python
class TestAdminAuth(unittest.TestCase):
    def _client(self, key="secret-key"):
        from app.db import config
        config.settings.ADMIN_API_KEY = key
        from app.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_login_rejects_wrong_password(self):
        client = self._client()
        resp = client.post("/api/admin/login", json={"password": "nope"})
        self.assertEqual(resp.status_code, 403)

    def test_login_accepts_correct_password(self):
        client = self._client()
        resp = client.post("/api/admin/login", json={"password": "secret-key"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])

    def test_logs_requires_admin_header(self):
        client = self._client()
        resp = client.get("/api/admin/logs")
        self.assertEqual(resp.status_code, 403)

    def test_kb_create_validates_empty(self):
        client = self._client()
        resp = client.post("/api/admin/kb", json={"question": "", "answer": ""},
                           headers={"X-Admin-Key": "secret-key"})
        self.assertEqual(resp.status_code, 400)
```

- [ ] **Step 4: Run the admin API tests**

Run: `cd backend && python -m pytest tests/test_admin_api.py -v`
Expected: PASS. (Requires `.env` + Neon reachable, since importing `app.main` constructs `faq_service`. The empty-field test returns 400 before any DB write.)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/admin.py backend/app/main.py backend/tests/test_admin_api.py
git commit -m "feat(admin): admin API router (login, logs, KB CRUD, export) + wiring"
```

---

## Task 7: Frontend admin page

**Files:**
- Create: `frontend/app/admin/page.tsx`
- Create: `frontend/app/admin/admin.module.css`

**Interfaces:**
- Consumes backend routes via the existing proxy at `/api/...` (no direct backend URL). Sends `X-Admin-Key` header from `sessionStorage`.
- Produces: the `/admin` page (login + dashboard).

- [ ] **Step 1: Create the admin page component**

Create `frontend/app/admin/page.tsx`:

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import styles from "./admin.module.css";

type Log = {
  id: string;
  question: string;
  answer: string;
  answered: boolean;
  top_score: number | null;
  resolved_at: string | null;
  created_at: string | null;
};

type KbEntry = { id: string; question: string; answer: string };
type Status = "all" | "answered" | "unanswered";

const KEY_STORAGE = "votage_admin_key";

export default function AdminPage() {
  const [adminKey, setAdminKey] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");

  const [tab, setTab] = useState<"logs" | "kb">("logs");
  const [status, setStatus] = useState<Status>("unanswered");
  const [search, setSearch] = useState("");
  const [logs, setLogs] = useState<Log[]>([]);
  const [kb, setKb] = useState<KbEntry[]>([]);
  const [editing, setEditing] = useState<{ question: string; answer: string; fromLogId?: string; kbId?: string } | null>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    setAdminKey(sessionStorage.getItem(KEY_STORAGE));
  }, []);

  const authHeaders = useCallback(
    () => ({ "Content-Type": "application/json", "X-Admin-Key": adminKey ?? "" }),
    [adminKey]
  );

  const signOut = () => {
    sessionStorage.removeItem(KEY_STORAGE);
    setAdminKey(null);
    setPassword("");
  };

  async function onLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoginError("");
    const res = await fetch("/api/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (!res.ok) {
      setLoginError("Incorrect password. Please try again.");
      return;
    }
    sessionStorage.setItem(KEY_STORAGE, password);
    setAdminKey(password);
  }

  const loadLogs = useCallback(async () => {
    if (!adminKey) return;
    const params = new URLSearchParams({ status, limit: "200" });
    if (search.trim()) params.set("q", search.trim());
    const res = await fetch(`/api/admin/logs?${params.toString()}`, { headers: authHeaders() });
    if (res.status === 403) return signOut();
    if (res.ok) setLogs(await res.json());
  }, [adminKey, status, search, authHeaders]);

  const loadKb = useCallback(async () => {
    if (!adminKey) return;
    const res = await fetch("/api/admin/kb", { headers: authHeaders() });
    if (res.status === 403) return signOut();
    if (res.ok) setKb(await res.json());
  }, [adminKey, authHeaders]);

  useEffect(() => { if (adminKey && tab === "logs") void loadLogs(); }, [adminKey, tab, loadLogs]);
  useEffect(() => { if (adminKey && tab === "kb") void loadKb(); }, [adminKey, tab, loadKb]);

  async function saveEntry() {
    if (!editing) return;
    const isEdit = Boolean(editing.kbId);
    const url = isEdit ? `/api/admin/kb/${editing.kbId}` : "/api/admin/kb";
    const res = await fetch(url, {
      method: isEdit ? "PUT" : "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        question: editing.question,
        answer: editing.answer,
        from_log_id: editing.fromLogId ?? null,
      }),
    });
    if (res.status === 403) return signOut();
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setNotice(body.detail || "Could not save. Please try again.");
      return;
    }
    setEditing(null);
    setNotice("Saved to knowledge base. The bot can use it now.");
    void loadLogs();
    void loadKb();
  }

  async function deleteEntry(id: string) {
    const res = await fetch(`/api/admin/kb/${id}`, { method: "DELETE", headers: authHeaders() });
    if (res.status === 403) return signOut();
    if (res.ok) void loadKb();
  }

  function exportFaq() {
    // Trigger a download through the proxy with the admin header.
    fetch("/api/admin/kb/export", { headers: authHeaders() })
      .then((r) => (r.ok ? r.blob() : Promise.reject()))
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "faq.md";
        a.click();
        URL.revokeObjectURL(a.href);
      })
      .catch(() => setNotice("Export failed. Please try again."));
  }

  if (!adminKey) {
    return (
      <main className={styles.loginWrap}>
        <form onSubmit={onLogin} className={styles.loginCard}>
          <h1 className={styles.title}>Admin Login</h1>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Admin password"
            className={styles.control}
            autoFocus
          />
          {loginError && <p className={styles.error}>{loginError}</p>}
          <button type="submit" className={styles.primaryBtn}>Sign in</button>
        </form>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>Chat History & Knowledge</h1>
        <div className={styles.headerActions}>
          <button onClick={exportFaq} className={styles.secondaryBtn}>Export faq.md</button>
          <button onClick={signOut} className={styles.secondaryBtn}>Sign out</button>
        </div>
      </header>

      {notice && <div className={styles.notice} onClick={() => setNotice("")}>{notice}</div>}

      <nav className={styles.tabs}>
        <button className={tab === "logs" ? styles.tabActive : styles.tab} onClick={() => setTab("logs")}>Chat history</button>
        <button className={tab === "kb" ? styles.tabActive : styles.tab} onClick={() => setTab("kb")}>Knowledge base</button>
      </nav>

      {tab === "logs" && (
        <>
          <div className={styles.controls}>
            {(["unanswered", "answered", "all"] as Status[]).map((s) => (
              <button key={s} className={status === s ? styles.chipActive : styles.chip} onClick={() => setStatus(s)}>
                {s}
              </button>
            ))}
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search questions..."
              className={styles.search}
            />
          </div>
          <div className={styles.list}>
            {logs.map((log) => (
              <div key={log.id} className={styles.row}>
                <div className={styles.rowMain}>
                  <p className={styles.q}>{log.question}</p>
                  <p className={styles.a}>{log.answer}</p>
                  <div className={styles.meta}>
                    <span className={log.answered ? styles.badgeOk : styles.badgeGap}>
                      {log.answered ? "answered" : "unanswered"}
                    </span>
                    {log.resolved_at && <span className={styles.badgeResolved}>resolved</span>}
                    <span className={styles.date}>{log.created_at?.slice(0, 16).replace("T", " ")}</span>
                  </div>
                </div>
                <button
                  className={styles.primaryBtn}
                  onClick={() => setEditing({ question: log.question, answer: log.answered ? log.answer : "", fromLogId: log.id })}
                >
                  Answer / Edit
                </button>
              </div>
            ))}
            {logs.length === 0 && <p className={styles.empty}>No questions in this view yet.</p>}
          </div>
        </>
      )}

      {tab === "kb" && (
        <div className={styles.list}>
          <button className={styles.primaryBtn} onClick={() => setEditing({ question: "", answer: "" })}>
            + New entry
          </button>
          {kb.map((entry) => (
            <div key={entry.id} className={styles.row}>
              <div className={styles.rowMain}>
                <p className={styles.q}>{entry.question}</p>
                <p className={styles.a}>{entry.answer}</p>
              </div>
              <div className={styles.headerActions}>
                <button className={styles.secondaryBtn} onClick={() => setEditing({ question: entry.question, answer: entry.answer, kbId: entry.id })}>Edit</button>
                <button className={styles.dangerBtn} onClick={() => void deleteEntry(entry.id)}>Delete</button>
              </div>
            </div>
          ))}
          {kb.length === 0 && <p className={styles.empty}>No admin entries yet.</p>}
        </div>
      )}

      {editing && (
        <div className={styles.modalBackdrop} onClick={() => setEditing(null)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.title}>{editing.kbId ? "Edit entry" : "Write answer"}</h2>
            <label className={styles.label}>Question</label>
            <textarea
              className={styles.textarea}
              value={editing.question}
              onChange={(e) => setEditing({ ...editing, question: e.target.value })}
            />
            <label className={styles.label}>Answer</label>
            <textarea
              className={styles.textarea}
              value={editing.answer}
              onChange={(e) => setEditing({ ...editing, answer: e.target.value })}
              rows={6}
            />
            <div className={styles.headerActions}>
              <button className={styles.secondaryBtn} onClick={() => setEditing(null)}>Cancel</button>
              <button className={styles.primaryBtn} onClick={() => void saveEntry()}>Save to knowledge base</button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Create the stylesheet**

Create `frontend/app/admin/admin.module.css`:

```css
.page { max-width: 960px; margin: 0 auto; padding: 24px 16px 80px; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
.loginWrap { min-height: 100vh; display: grid; place-items: center; background: #f5f6f8; padding: 16px; }
.loginCard { width: min(400px, 100%); background: #fff; border: 1px solid #e5e7eb; border-radius: 14px; padding: 28px; display: flex; flex-direction: column; gap: 12px; box-shadow: 0 10px 30px rgba(0,0,0,.06); }
.header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.headerActions { display: flex; gap: 8px; }
.title { font-size: 20px; font-weight: 800; margin: 0; }
.tabs { display: flex; gap: 8px; border-bottom: 1px solid #e5e7eb; margin-bottom: 16px; }
.tab, .tabActive { background: none; border: none; padding: 10px 14px; cursor: pointer; font-weight: 700; color: #6b7280; border-bottom: 2px solid transparent; }
.tabActive { color: #111827; border-bottom-color: #2563eb; }
.controls { display: flex; gap: 8px; align-items: center; margin-bottom: 14px; flex-wrap: wrap; }
.chip, .chipActive { text-transform: capitalize; border: 1px solid #d1d5db; background: #fff; border-radius: 999px; padding: 6px 14px; cursor: pointer; font-size: 13px; }
.chipActive { background: #111827; color: #fff; border-color: #111827; }
.search { flex: 1; min-width: 180px; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 8px; }
.list { display: flex; flex-direction: column; gap: 10px; }
.row { display: flex; gap: 12px; align-items: flex-start; justify-content: space-between; background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 14px; }
.rowMain { flex: 1; min-width: 0; }
.q { font-weight: 700; margin: 0 0 4px; }
.a { color: #4b5563; margin: 0 0 8px; white-space: pre-wrap; }
.meta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.badgeOk { background: #d1fae5; color: #065f46; border-radius: 999px; padding: 2px 10px; font-size: 12px; font-weight: 700; }
.badgeGap { background: #fee2e2; color: #991b1b; border-radius: 999px; padding: 2px 10px; font-size: 12px; font-weight: 700; }
.badgeResolved { background: #dbeafe; color: #1e40af; border-radius: 999px; padding: 2px 10px; font-size: 12px; font-weight: 700; }
.date { color: #9ca3af; font-size: 12px; }
.empty { color: #9ca3af; padding: 24px; text-align: center; }
.control, .textarea { width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 8px; font: inherit; }
.textarea { resize: vertical; margin-bottom: 10px; }
.label { font-size: 13px; font-weight: 700; color: #374151; display: block; margin: 6px 0 4px; }
.primaryBtn { background: #2563eb; color: #fff; border: none; border-radius: 8px; padding: 9px 14px; font-weight: 700; cursor: pointer; }
.secondaryBtn { background: #fff; color: #111827; border: 1px solid #d1d5db; border-radius: 8px; padding: 9px 14px; font-weight: 700; cursor: pointer; }
.dangerBtn { background: #fff; color: #b91c1c; border: 1px solid #fca5a5; border-radius: 8px; padding: 9px 14px; font-weight: 700; cursor: pointer; }
.error { color: #b91c1c; font-size: 13px; margin: 0; }
.notice { background: #eef2ff; color: #3730a3; border: 1px solid #c7d2fe; border-radius: 10px; padding: 10px 14px; margin-bottom: 14px; cursor: pointer; font-weight: 600; }
.modalBackdrop { position: fixed; inset: 0; background: rgba(0,0,0,.4); display: grid; place-items: center; padding: 16px; z-index: 50; }
.modal { width: min(640px, 100%); background: #fff; border-radius: 14px; padding: 22px; max-height: 90vh; overflow: auto; }
```

- [ ] **Step 3: Verify the frontend builds/lints**

Run: `cd frontend && npx next lint --dir app/admin`
Expected: no errors for `app/admin` (warnings acceptable).

- [ ] **Step 4: Commit**

```bash
git add frontend/app/admin/page.tsx frontend/app/admin/admin.module.css
git commit -m "feat(admin): /admin page (login, history filter, KB editor, export, sign out)"
```

---

## Task 8: End-to-end verification + changelog

**Files:**
- Modify: `CHANGE_LOG.md`

- [ ] **Step 1: Run the full backend test suite**

Run: `cd backend && python -m pytest tests/test_kb_helpers.py tests/test_admin_api.py -v`
Expected: all PASS (pure-logic tests always; API/service tests pass with `.env` + Neon reachable).

- [ ] **Step 2: Manual end-to-end check**

Start backend (`cd backend && PYTHONUTF8=1 uvicorn app.main:app --reload`) and frontend (`cd frontend && npm run dev`), then in a browser:
1. Visit `/admin` → enter the `ADMIN_API_KEY` password → dashboard loads.
2. Filter to **unanswered**; pick a question; click **Answer / Edit**; write an answer; **Save**.
3. Open the public chat and ask that question → bot now answers it (live, no restart).
4. Confirm the answered log shows a **resolved** badge.
5. Go to **Knowledge base** tab → the entry is listed; edit it → confirm the chat answer updates; delete a throwaway entry → it disappears and the bot stops using it.
6. Click **Export faq.md** → open the downloaded file → it contains the full seed plus a `# Source: admin` section with your entry, no duplicates.
7. Click **Sign out** → returns to login; refresh → still logged out.

Expected: every step behaves as described.

- [ ] **Step 3: Update the changelog**

Add an entry to `CHANGE_LOG.md` summarizing: admin chat-history page; DB-backed KB additions (live, deploy-safe) with vector upsert; status/keyword filtering + mark-resolved; full `faq.md` export; shared-password auth via `X-Admin-Key`.

- [ ] **Step 4: Commit**

```bash
git add CHANGE_LOG.md
git commit -m "docs(admin): changelog for chat-history review & KB editing feature"
```

---

## Self-Review Notes

- **Spec coverage:** §2 storage → Tasks 1,3,4,5; §3 auth → Task 6 (`require_admin`, `/admin/login`) + Task 7 (sessionStorage); §4 data model → Task 1; §5 endpoints → Task 6; §6 FAQService → Task 4; §7 export → Tasks 2,6,7; §8 frontend → Task 7; §9 error handling → validation (Task 5), defensive live-index updates (Task 6); §10 testing → Tasks 2,4,6,8. All sections covered.
- **Auth note:** `require_admin` is duplicated in `admin.py` rather than imported from `chat.py` to keep the new router self-contained; the existing `chat.py` gate is left untouched.
- **Type consistency:** `kb_entry_to_chunk` id format `admin:{id}` is used identically in Task 4 (`add_entry`/`remove_entry`) and Task 2. CRUD returns dicts with `id` as `str`, matching what `faq_service.add_entry`/`update_entry` expect.
- **Live-index resilience:** KB writes commit to the DB first; the live-index update is wrapped so a transient embed/vector failure leaves the DB row intact (the entry still appears after the next backend restart via `_load_kb_chunks`).
