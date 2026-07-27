# Admin Chat-History & Knowledge Review — Design Spec

**Date:** 2026-06-30
**Branch:** `feature/admin-chat-history`
**Status:** Approved design, ready for implementation planning

## 1. Problem & Goal

The church chatbot answers visitor questions from a knowledge base (`faq.md` + a
pgvector index). Today there is no way for the internal tech team to see what
visitors are actually asking, which questions the bot could **not** answer, or to
fix those gaps without manually editing `faq.md`, restarting the backend, and
rebuilding the vector index.

**Goal:** a private admin page where the team can, anytime and from any machine:

1. Review the full chat history (every question + the bot's answer).
2. Filter by answered / unanswered and search by keyword.
3. Author an answer for an unanswered (or any) question — editing both the
   question text and the answer — and save it into the knowledge base so the bot
   uses it **immediately**, with no restart and no risk of being lost on the next
   deploy.
4. Keep the git-tracked `faq.md` in sync on their own schedule via an export.

## 2. Key Architectural Decision: store admin answers in the database, not `faq.md`

The bot reads knowledge from two live sources that mirror each other:

- **`faq.md`** — read into memory once at backend startup; tracked in git.
- **`faq_embeddings`** (pgvector table in Neon) — the semantic index, shared by
  both the local backend and the deployed AWS backend.

Writing admin answers **directly into `faq.md`** is rejected because:

- The write lands on whatever server runs the backend (the AWS box when using the
  live site, **not** the admin's laptop).
- `faq.md` is tracked in git, so the **next deploy overwrites it** — admin answers
  would be silently lost.
- It requires a backend restart + index rebuild to take effect, and risks
  file-write races and local/server divergence.

**Decision:** admin-authored Q&A is written to a new **`kb_entries`** database
table and embedded into the existing **`faq_embeddings`** table. Because both live
in the shared Neon database:

| Property | Write to `faq.md` (file) | Write to DB (chosen) |
| --- | --- | --- |
| Survives a redeploy | No — overwritten | Yes — persistent |
| Works from local *and* live site | No — wrong machine | Yes — same Neon DB |
| Bot picks it up | Needs restart + rebuild | Immediately, live |
| Git divergence / file races | Yes | None |

`faq.md` remains the git-managed **seed** knowledge. Admin additions are a durable
**second layer** in the DB. An export step (section 7) folds the DB layer back into
`faq.md` whenever the team wants git to catch up.

The save into `kb_entries` is **permanent** — it persists through restarts and
deploys until explicitly deleted. The only thing that lags is `faq.md` catching up,
which is purely a backup/version-control convenience, not a functional gap.

## 3. Authentication: single shared password

- Reuses the existing `ADMIN_API_KEY` setting as the shared admin password — no new
  secret to introduce. The backend already has a `require_admin` dependency that
  checks the `X-Admin-Key` header and denies by default when the key is unset.
- **Login:** the admin enters the password on `/admin`. The frontend verifies it via
  `POST /api/admin/login`, then stores it in the browser's `sessionStorage`.
- **Per-request auth:** every admin API call sends the password as the `X-Admin-Key`
  header. The existing Next.js proxy (`app/api/[...path]/route.js`) already forwards
  arbitrary headers to the backend unchanged.
- **Sign out:** clears `sessionStorage` and returns to the login screen. Because the
  value lives in `sessionStorage` (not `localStorage`), closing the tab also logs the
  admin out automatically.
- **Wrong password:** friendly inline error, no access granted.

This is appropriate for an internal team tool and is consistent with the existing
admin gate. (Future upgrade path, out of scope: per-user accounts / token sessions.)

## 4. Data Model Changes

### New table: `kb_entries`
The permanent home for admin-authored knowledge.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | default uuid4 |
| `question` | Text | not null |
| `answer` | Text | not null |
| `source` | String(80) | default `"admin"` |
| `created_at` | DateTime(tz) | server default now() |
| `updated_at` | DateTime(tz) | updated on edit |
| `exported_at` | DateTime(tz) | nullable; set when folded into `faq.md` |

### Modified table: `chat_logs`
Add one nullable column to support "mark resolved":

| Column | Type | Notes |
| --- | --- | --- |
| `resolved_at` | DateTime(tz) | nullable; set when an admin answers this gap |

Both changes ship as an Alembic migration consistent with the existing
`backend/alembic/versions` setup. The corresponding `faq_embeddings` row for a KB
entry is keyed by a deterministic id (e.g. `admin:{kb_entry_id}`) so edits/deletes
can target it precisely.

## 5. Backend API (all admin-gated via `require_admin`)

Grouped under an `/api/admin` router for clarity; the existing `/api/faq/logs`
endpoint is superseded by `/api/admin/logs` (kept working or redirected during
transition).

- `POST /api/admin/login`
  Body `{ password }`. Returns `{ ok: true }` on match, `403` otherwise. Used only
  for immediate login feedback; real auth remains the per-request header.

- `GET /api/admin/logs?status=all|answered|unanswered&q=<keyword>&limit=<n>`
  Returns recent chat logs (newest first) including `resolved_at`. Extends the
  existing `get_logs` with keyword filtering on the question text.

- `POST /api/admin/kb`
  Body `{ question, answer, from_log_id? }`. Validates non-empty, length-capped
  inputs; inserts into `kb_entries`; embeds the Q&A and upserts the vector into
  `faq_embeddings`; adds it to the FAQ service's live in-memory chunks (no restart);
  if `from_log_id` is provided, stamps that chat log's `resolved_at`. Returns the
  created entry.

- `GET /api/admin/kb`
  Lists admin-authored entries (newest first) for review/management.

- `PUT /api/admin/kb/{id}`
  Edits a saved entry: updates the row, re-embeds, replaces the `faq_embeddings`
  vector, refreshes the live chunk. Lets the team fix a wrong/typo'd answer.

- `DELETE /api/admin/kb/{id}`
  Removes the entry, its `faq_embeddings` vector, and the live chunk.

- `GET /api/admin/kb/export`
  Returns the **complete, de-duplicated** `faq.md` (seed content + all `kb_entries`,
  merged, admin entries under a `# Source: admin` section). Served as a file
  download. Stamps `exported_at` on the included entries (used only as a hint; the
  export is always a full, self-contained file).

All write paths follow the codebase's existing defensive pattern: a logging or
embedding failure is caught and never breaks the request or the page.

## 6. FAQ Service Changes (`backend/app/services/faq/faq.py`)

- `_load_faq_chunks()` (or a new combined loader) loads `faq.md` chunks **plus** all
  `kb_entries` rows at startup, so both lexical and holistic-context paths see admin
  knowledge. Existing `(question, answer)` de-duplication already prevents doubles
  when an entry exists in both `faq.md` and the DB.
- New `add_entry(question, answer)` / `update_entry` / `remove_entry` methods mutate
  the in-memory chunk list and rebuild the small derived vocab, so live edits take
  effect within the running process without a restart.
- Embedding uses the existing `OpenAIEmbedder`; vector upsert uses the existing
  `PgVectorRetriever.store_vectors` (extended to upsert on conflict for edits).

## 7. Keeping `faq.md` / git in sync (export workflow)

```
admins add/edit answers  ->  live in DB, bot uses them instantly (permanent)
        |
   (whenever the team wants: daily / weekly / before a deploy)
        v
GET /api/admin/kb/export  ->  download complete faq.md  ->  replace local file
        v
git add backend/app/data/faq.md && git commit && git push
```

- The download is **always the full knowledge base** (cumulative), so the team never
  hand-merges — they replace `faq.md` with the download, commit, and push.
- De-duplication by question text guarantees an entry that is already in `faq.md`
  (because a prior export was committed and deployed) is not written twice.
- Day-to-day this is optional; the bot works regardless. Export exists to keep git as
  the durable master/backup.

## 8. Frontend Changes (Next.js App Router)

- New route `frontend/app/admin/page.tsx` (client component), following the styling
  patterns in `app/register/page.tsx`.
- **Login view** when no password is in `sessionStorage`: password field + sign-in
  button, inline error on failure.
- **Dashboard view** when authenticated:
  - Header with a **Sign out** button.
  - Filter controls: All / Answered / Unanswered tabs, keyword search box.
  - Table of chat logs: question, answer, status badge, score, timestamp, resolved
    badge. Newest first.
  - Row action **Answer / Edit** opens an editor (modal or inline) pre-filled with
    the question + answer, both editable, with **Save to knowledge base**.
  - A **Knowledge Base** section/tab listing admin-authored entries with edit/delete.
  - An **Export faq.md** button that downloads the file.
- All admin requests attach the `X-Admin-Key` header from `sessionStorage`; a `403`
  response forces a return to the login view.

## 9. Error Handling & Edge Cases

- Empty or whitespace-only question/answer rejected with a clear message.
- Over-long inputs capped (reasonable limit, e.g. a few thousand chars).
- Embedding/DB write failure on save: surfaced to the admin as a retryable error;
  never crashes the page; never leaves a half-written entry (transactional insert +
  embed, or insert recorded and vector retried).
- Stale Neon connections reuse the existing self-healing reconnect logic in
  `PgVectorRetriever`.
- Wrong/missing admin key on any admin endpoint returns `403` (deny by default).

## 10. Testing

- **Unit:** FAQ service `add_entry` / `update_entry` / `remove_entry` update chunks
  correctly; export produces a complete, de-duplicated `faq.md`; admin auth gate
  rejects missing/wrong keys and accepts the correct one.
- **Integration:** `POST /api/admin/kb` inserts the row, upserts the vector, and the
  bot answers the newly added question on the next ask.
- **Manual:** end-to-end run of login -> view/filter -> answer an unanswered question
  -> confirm the bot now answers it -> export `faq.md` -> verify the file is complete
  and de-duplicated -> sign out.

## 11. Out of Scope (explicitly deferred)

- Per-user admin accounts / token-based sessions (single shared password is the
  agreed v1).
- Automatic git commit/push of `faq.md` from the server (export + manual push is
  intentional, to keep the server out of the git workflow).
- Analytics/aggregate dashboards over the chat logs.
