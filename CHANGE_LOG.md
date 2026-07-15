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
| **Answer behavior** | Confidently wrong on anything not in the KB | Answers church facts from the KB; gives warm general guidance for everyday questions; defers personal/pastoral & unknown church facts to an admin | Helpful *and* honest — never invents church facts |
| **Question history** | Nothing captured — every question forgotten | Every question logged + an admin view of the unanswered gaps | See what the bot couldn't answer, and improve it |
| **Security** | Chat-logs endpoint open to anyone | Requires a secret admin key (locked by default) | Visitors' questions/answers are protected |
| **Admin workflow** | No UI — gaps could only be seen via a raw API call | An `/admin` page: log in, browse/filter chat history, write answers that go live instantly, export `faq.md` | The team can improve the bot anytime, from any machine, with no restart or deploy |
| **Sign-in error feedback** | When someone failed to register or check in on Sunday, there was no record — we couldn't reproduce or diagnose it | Every failed registration/check-in is captured (the exact error the person saw + the details they typed) and shown in a new admin tab, with "Mark handled" | We can finally see and fix Sunday sign-in problems instead of guessing — the feedback system the team asked for |

_Details for each of these are in the sections below (see §6)._

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

### Bugfix: stale DB connection caused a misleading "too many requests" error (APPLIED)

Root cause: the vector-search code held **one long-lived database connection**; Neon drops idle connections, so after a while every meaning-search threw `connection already closed`. Uncovered questions then fell through to a 503, which the frontend mislabels as *"I'm receiving too many requests"* — so it looked like a rate limit but wasn't. (Covered questions still worked because the keyword backup answered them — which is why only "wrong" questions showed the error.)

- **`backend/app/rag/retriever.py`** — the retriever now **reconnects automatically** if its connection is stale, and retries the query once.
- **`backend/app/services/faq/faq.py`** — on any unrecoverable error, reply with the friendly *"I don't have that information yet…"* message instead of a scary 503.

_Verified: "Can I bring my dog", "Who is in charge of drums" now reply honestly; covered questions still answer._

### Tuning: answer church shorthand like "connect" (APPLIED)

The strict answer prompt was over-refusing valid shorthand — e.g. "What is a connect?" was declined even though Connect Group content was retrieved with a strong 0.62 similarity score. Updated `backend/app/rag/generator.py` to interpret the question reasonably (treat "connect" as "Connect Group"), while still declining genuinely-uncovered topics.

_Verified battery: "connect" / "connect group" / "meet people" / location all answer; "wear" / "parking" / "dog" / "drums" still decline._

### Answer policy: warm general answers + defer personal/unknown (APPLIED — supersedes the strict "decline everything not in the KB" above)

Per the team's direction, broadened the bot from "only answer from the KB" to a warm assistant with **three behaviors**:
- **Church-specific facts** → answer from `faq.md`; if not in the KB, **defer to admin** (never invent).
- **General / common-sense** questions (dress, etiquette, broadly-Christian) → warm, faith-appropriate **general answer**.
- **Personal / pastoral** (counselling, prayer, spiritual advice, sensitive) → **defer to admin**.

- **`backend/app/rag/generator.py`** — rewrote the answer prompt to follow the three buckets above (and never fabricate church-specific facts).
- **`backend/app/services/faq/faq.py`** — removed the hard "skip-the-LLM" relevance floor so general questions reach the model (the model now decides answer vs defer); removed the now-unused `RELEVANCE_FLOOR`.
- **`backend/app/data/faq.md`** — added the church's pet/dog policy (so it answers consistently).
- **Holistic context:** the model now receives the **whole knowledge base** on every question (not just the closest few entries), so it reasons about the church as a whole and connects partial/related terms — e.g. "refresh" → Refresh Miracle Service & Tour, "what time is church" → service times, "growth track" → the membership class. The answer prompt was also told to match partial/shortened names to the fuller item. (Works because the KB is small; if it grows very large we'd reintroduce selective retrieval.)

_Verified: "refresh" / "the refresh" / "growth track" / "what time is church" now answer by connecting related entries; church facts answer; general questions answer warmly; counselling / prayer-request / unknown facts (wifi) still defer to admin._

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

## 5. Admin chat-history & knowledge review (branch `feature/admin-chat-history`) — APPLIED & tested

**What it is:** a private `/admin` page where the tech team logs in (single shared password = the existing `ADMIN_API_KEY`), reviews every question visitors asked, filters by answered/unanswered, and **writes answers for the gaps**. A saved answer is used by the bot **immediately** — no restart, no redeploy.

**Key design decision — answers are stored in the database, not `faq.md`:**
Admin answers go into a new `kb_entries` table and are embedded into the existing `faq_embeddings` index. This is deliberate: the live/AWS backend and a local laptop share the same Neon database, and `faq.md` is git-tracked — so writing to `faq.md` at runtime would be overwritten (and lost) on the next deploy. DB storage is permanent and works from either machine. `faq.md` stays the git-managed "seed"; admin additions are a durable second layer. An **Export faq.md** button regenerates the complete, de-duplicated file so the team can commit it to git on their own schedule.

**Code changes:**

| # | File | Change |
|---|------|--------|
| 1 | `backend/app/db/models.py` | Added `KbEntry` model; added `resolved_at` to `ChatLog` |
| 2 | `backend/app/rag/db_init.py` | Startup DDL: `CREATE TABLE kb_entries`; `ALTER TABLE chat_logs ADD COLUMN resolved_at` |
| 3 | `backend/app/services/faq/kb.py` | New: pure helpers (normalize/parse/chunk/export-render) + DB CRUD (create/list/update/delete) |
| 4 | `backend/app/services/faq/logs.py` | `get_logs` now takes `status`+`q` (keyword) and returns `resolved_at`; added `mark_resolved` |
| 5 | `backend/app/rag/retriever.py` | Added `upsert_vector` (insert-or-replace) and `delete_vector` |
| 6 | `backend/app/services/faq/faq.py` | Loads `kb_entries` at startup; `add_entry`/`update_entry`/`remove_entry` update the live index; `read_seed_markdown` |
| 7 | `backend/app/api/admin.py` | New admin router: `POST /admin/login`, `GET /admin/logs`, `GET/POST/PUT/DELETE /admin/kb`, `GET /admin/kb/export` (all gated by `X-Admin-Key`) |
| 8 | `backend/app/api/chat.py` | Updated `/faq/logs` call to the new `get_logs(status=...)` signature |
| 9 | `backend/app/main.py` | Registered the admin router |
| 10 | `frontend/app/admin/page.tsx` + `admin.module.css` | New `/admin` page: login, history filter/search, answer/edit modal, KB management tab, export, sign out |

**Database changes:** new table `kb_entries` (id, question, answer, source, created_at, updated_at, exported_at); new column `chat_logs.resolved_at`. Both created idempotently at startup.

**Tests (all passing, 13):** `backend/tests/test_kb_helpers.py` (pure helpers + validation) and `backend/tests/test_admin_api.py` (FAQService live edits + admin auth gate). Verified end-to-end against the real Neon DB + OpenAI: full CRUD round-trip, admin API round-trip (create→list→export→delete), and the headline path — **an admin answer makes the bot answer a paraphrased question live**.

---

## 6. Check-in & registration error feedback (branch `feature/admin-chat-history`) — APPLIED & tested

**What it is:** an observability layer that records every **failed** registration and
check-in — the exact error the user saw plus the details they tried to use — into a
new `intake_issues` table, reviewable in a new admin tab. Requested by the team lead
after Sunday sign-in failures couldn't be reproduced. **Capture + review only** — no
changes to user-facing messages or the sign-in flows.

**Captured at the layer where the error is truthful:**
- **Visible popup/banner errors** (the red notice on the registration form; the chat
  widget's error states) — including "code-like but readable" 500s and errors that
  never reach our clean handlers (422 validation, proxy/network/rate-limit) — are
  reported by the **frontend** (the exact on-screen text) to a public
  `POST /api/intake-issues/report`. `reason` is derived server-side from the HTTP
  status (`409`→`phone_exists`, `422`→`validation_error`, `>=500`→`server_error`, else `ui_error`).
- **Silent check-in dead-ends** (unrecognized phone, connect-group mismatch) are
  *normal bot replies*, so they're captured **server-side** in `_record_checkin`.

**Code changes:**

| # | File | Change |
|---|------|--------|
| 1 | `backend/app/db/models.py` | Added `IntakeIssue` model (+ `Integer` import) |
| 2 | `backend/app/rag/db_init.py` | Startup DDL: `CREATE TABLE intake_issues` |
| 3 | `backend/app/services/intake/logs.py` | New: `derive_reason`, `report_intake_issue`, `log_checkin_failure`, `get_intake_issues`, `mark_intake_resolved` (defensive, own DB session) |
| 4 | `backend/app/services/checkin/check_in.py` | Thread `session_id` into `_record_checkin`; log the two failure returns |
| 5 | `backend/app/api/intake.py` | New public `POST /api/intake-issues/report` |
| 6 | `backend/app/api/admin.py` | `GET /admin/intake-issues`, `PATCH /admin/intake-issues/{id}/resolve` |
| 7 | `backend/app/main.py` | Registered the intake router |
| 8 | `frontend/lib/reportIssue.ts` | New best-effort client reporter |
| 9 | `frontend/app/register/page.tsx` | Report the registration error banner + submitted form |
| 10 | `frontend/components/ChatWidget.tsx` | Report check-in widget errors (guarded to the check-in instance) |
| 11 | `frontend/app/admin/page.tsx` | Third "Check-in & registration issues" tab: filter by kind, search phone/email/name, **Mark handled** |

**Database changes:** new table `intake_issues` (id, kind, reason, message, source,
http_status, phone, email, name, details, session_id, created_at, resolved_at),
created idempotently at startup.

**Privacy:** rows contain member PII (name, email, phone) — same sensitivity as the
`members` table, admin-gated behind the shared password. The report endpoint is
public (visitors call it) and insert-only into an admin-viewable table; message and
fields are length-capped. Flagged by an automated security review as
"sensitive-to-observability" — this is by design (the team explicitly wants the
details used to sign in), and the data travels the same network path the
registration POST already uses (no new exposure channel).

**Tests (all passing, 22 backend total):** `tests/test_intake.py` (reason derivation
+ admin auth-gate). Verified end-to-end against the real Neon DB: a client-reported
registration failure and a real unregistered-phone check-in both appear in the admin
tab with correct kinds/reasons; kind filters and "Mark handled" work.

**Deferred:** Slack forwarding (capture path kept reusable); any user-facing message
changes (e.g. "you're already registered — please check in").

---

## 7. Operational notes / gotchas

- **ProtonVPN must be OFF** while working locally — it blocks the Neon database connection (port 5432). This cost a lot of debugging time.
- Run the backend with the venv (`backend/.venv`); the emoji crash is fixed in `main.py`.
- Frontend dev server is on **http://localhost:3001** (3000 was in use).
- Restart commands:
  - Backend: `cd backend` → `.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000`
  - Frontend: `cd frontend` → `npm run dev`
