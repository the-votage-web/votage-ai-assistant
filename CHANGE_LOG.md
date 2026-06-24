# Change Log — accuracy work (branch `fix/faq-accuracy`)

> A running record of **every change we make to the code and the database**, so anyone
> (you or a teammate) can see exactly what was touched and why. Companion to
> `CODEBASE_OVERVIEW.md` (which explains how the whole system works).
>
> _Started: 2026-06-23. Branch: `fix/faq-accuracy` (off `main`)._

---

## At a glance — what changed and why

| Area | Before | After | Why it's better |
|---|---|---|---|
| **Runs on Windows** | Crashed on startup (emoji in logs) | UTF-8 output fix | The app actually starts on Windows |
| **Search quality** | Keyword matching only (vector store empty) | `faq.md` embedded (34 entries) | Finds answers by **meaning**, not just shared words |
| **Accuracy** | Confidently wrong on questions it didn't know ("what should I wear?" → Connect Groups) | Honest "I don't have that information" when a topic isn't covered | **Honest instead of wrong** |
| **Question history** | Nothing captured — every question forgotten | Every question logged + an admin view of the unanswered gaps | See what the bot couldn't answer, and improve it |
| **Security** | Chat-logs endpoint open to anyone | Requires a secret admin key (locked by default) | Visitors' questions/answers are protected |

_Details for each of these are in the sections below._

---

## 1. Code changes

| # | File | Change | Why | Committed? |
|---|------|--------|-----|-----------|
| 1 | `backend/app/main.py` | Added a UTF-8 reconfigure of `stdout`/`stderr` at the top | The app prints emoji (`✅ 🚀`) on startup, which crashes on Windows' default console (`UnicodeEncodeError`). This makes it run cleanly on Windows. Behavior-neutral. | Not yet committed |
| 2 | `backend/app/db/config.py`, `backend/alembic/env.py` | **Teammate's change**, merged in from `main` (commit "change config to parameters") | Config now reads separate DB parameters (`DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_SSLMODE`, `DB_OPTIONS`, `DB_CHANNEL_BINDING`) and assembles the connection URL itself. | On `origin/main` (merged into our branch) |
| 3 | `backend/.env.example` | New file — safe template listing required env var names (no secrets) | So teammates know what to configure | Committed on branch |
| 4 | `CODEBASE_OVERVIEW.md` | New doc — explains architecture, the RAG/FAQ flow, and findings | Onboarding / shared understanding | Local only (not pushed, by request) |
| 5 | `CHANGE_LOG.md` (this file) | New doc — running record of changes | Transparency on code + DB changes | Local only (for now) |

**Not committed / local-only (gitignored, never pushed):**
- `backend/.env` — real secrets (DB params, OpenAI key).
- `frontend/.env.local` — `NEXT_PUBLIC_API_BASE` (empty) + `BACKEND_URL=http://localhost:8000`.

### Accuracy + question-logging (step c — APPLIED & tested)

- **`backend/app/services/faq/faq.py`** — `ask()` now replies honestly ("I don't have that information yet…") when nothing relevant is found, instead of returning the nearest unrelated answer. It uses a low vector-score floor (`RELEVANCE_FLOOR = 0.20`) plus the model's own relevance judgment. `handle_faq()` now logs every question via `log_chat`.
- **`backend/app/rag/generator.py`** — stricter answer prompt: answer only from the provided context, otherwise reply "I don't have enough information."
- **`backend/app/db/models.py`** — added the `ChatLog` model (+ `Float` import).
- **`backend/app/rag/db_init.py`** — creates the `chat_logs` table on startup.
- **`backend/app/services/faq/logs.py`** (new file) — `log_chat()` writes one row per question; `get_logs()` reads them back.
- **`backend/app/api/chat.py`** — new endpoint `GET /api/faq/logs` (and `?unanswered=true`) to review chat history and the unanswered gaps.

_Verified locally: covered questions still answer; "what should I wear / parking / dog / wifi" now reply honestly; every question is logged with an `answered` flag + score._

### Security: admin-gate on the chat-logs endpoint (APPLIED)

A background security review flagged that `GET /api/faq/logs` was unauthenticated — that's information disclosure, since chat logs can contain personal details. Fixed:
- **`backend/app/api/chat.py`** — added a `require_admin` dependency on `/api/faq/logs`: it requires an `X-Admin-Key` header matching `ADMIN_API_KEY`, and **denies by default** if no key is configured. Also capped `limit` at 500.
- **`backend/app/db/config.py`** — added the `ADMIN_API_KEY` setting.
- **`backend/.env` / `backend/.env.example`** — added `ADMIN_API_KEY` (the `.env` has a dev value; production must set a strong one). Also corrected the template's database block to the new `DB_*` parameter format (it was stale after the merge and would not have booted for a teammate).

_Verified: no key → 403, wrong key → 403, correct key → data; `/api/chat` stays public._

### Knowledge base updates (content)

- **`backend/app/data/faq.md`** — updated the church address to "The Winlos/Votage Center, by Ascend School, Airport Road Extension, Benin City," and added 15 Q&A pairs from the **Membership 101** handbook (church story, founders' bios, beliefs, vision/mission, core values).
- **`backend/app/ingestion/rebuild_index.py`** (new file) — a reusable command that re-syncs the vector store from `faq.md` (clears + re-embeds).
- **Maintenance rule:** `faq.md` is the single source of truth → edit it → run `python -m app.ingestion.rebuild_index` → restart the backend.
- _(Pending decision: the Workers Code of Conduct doc — internal/staff-facing — was NOT ingested; see §4.)_

---

## 2. Database changes

All against the **team's Neon database** (the connection string provided by the teammate). The team approved writing to it.

### Schema (created automatically by the app on startup — `db_init.py`)
- Enabled the **`pgvector`** extension (`CREATE EXTENSION IF NOT EXISTS vector`).
- Created table **`faq_embeddings`** `(id, question, answer, text, embedding vector(1536), metadata)`.
- Created index **`faq_embedding_idx`** on the embedding column.
- Created table **`chat_logs`** `(id, session_id, question, answer, answered, top_score, created_at)` — the question-logging table (step c). Auto-created on startup.
- All statements are `IF NOT EXISTS` (idempotent — safe to re-run; running twice changes nothing).

### Data
- **Inserted 34 rows into `faq_embeddings`** (table went 0 → 34) by embedding the existing `backend/app/data/faq.md` (the "vector store" / step b).
  - Used OpenAI `text-embedding-3-small`. No website scraping was done.
  - This is what lets the chatbot search by *meaning* instead of just keywords.
- **Re-embedded to 49 rows** after the knowledge-base update (address fix + Membership 101) via `rebuild_index.py` — the table is cleared and rebuilt from `faq.md`, so it always matches the file.

### What was NOT touched
- No other tables were created, modified, or read for writing.
- No rows were deleted or updated.
- Alembic migrations were **not** run (the app's other tables — members, registrations, services, connect groups — were untouched).

---

## 3. Local environment setup (no repo/code impact)

- Installed **Python 3.12** alongside the system's 3.14 (older pinned deps lack 3.14 support).
- Created the virtual environment at **`backend/.venv`** (Python 3.12) and installed `requirements.txt`, **excluding `chromadb`** (unused/dead code that needs a C++ compiler to build).
- Ran `npm install` in `frontend/`.
- Ran the backend (`uvicorn` on `:8000`) and frontend (`next dev` on **`:3001`** — port 3000 was occupied).
- Used two throwaway scripts (`_smoke.py`, `_ingest_local.py`) to test and to load the vector store; both were **deleted** afterward.

---

## 4. Still to do (planned)

- **Decide on the Workers Code of Conduct doc** — it's internal/staff-facing (worker rules, not visitor FAQ), so it was NOT ingested. Confirm whether the *public* chatbot should answer from it before adding. (Membership 101 is already ingested.)
- **(Optional) Clear test rows** from `chat_logs` before real use (it currently holds our local test questions).
- **(Optional) Commit & open a PR** for the accuracy + logging changes once you're happy.

---

## 5. Operational notes / gotchas

- **ProtonVPN must be OFF** while working locally — it blocks the Neon database connection (port 5432). This cost a lot of debugging time.
- Run the backend with the venv (`backend/.venv`); the emoji crash is fixed in `main.py`.
- Frontend dev server is on **http://localhost:3001** (3000 was in use).
- Restart commands:
  - Backend: `cd backend` → `.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000`
  - Frontend: `cd frontend` → `npm run dev`
