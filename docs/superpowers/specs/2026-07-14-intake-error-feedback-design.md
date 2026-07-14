# Check-in & Registration Error Feedback — Design Spec

**Date:** 2026-07-14
**Branch:** `feature/admin-chat-history` (bundled with the admin chat-history work — one PR)
**Status:** Approved design, ready for implementation planning

## 1. Problem & Goal

On Sundays, visitors fail to register or check in, and afterward the team cannot
reproduce the failures because there is no record of **what the person entered**
or **the exact error they saw**. Triage today is manual: look the person up by
email in Neon, spot a phone mismatch, and either tell them their registered
number or fix it in the SQL editor. Duplicate-phone people (already registered)
keep hitting the register error instead of checking in.

**Goal:** an observability layer that records every failed registration and
check-in with the user's input and the exact error message shown, viewable in a
private admin tab, so the team can see patterns, reproduce issues, and mark each
one handled. This is **capture + review only** — no changes to the user-facing
messages or the registration/check-in flows themselves.

## 2. Key Insight: capture at the layer where the error is truthful

Errors reach the user through two different paths, so we capture each where it is
most faithful:

- **Visible "popup"/banner errors** (the red notice at the top of the
  registration form, and any error state the chat widget flashes) — including
  "code-like but readable" text such as `Database schema error: …` or
  `Registration failed: …`, **and** errors that never reach our clean handlers
  (FastAPI 422 validation, proxy/network/rate-limit). These are captured **on the
  client**, which reports the exact on-screen text to the backend.
- **Silent check-in dead-ends** — "I don't recognize that phone number" and
  connect-group mismatch. These are *normal bot replies*, not red errors, so the
  frontend would not flag them. They are captured **on the server** at the point
  they are produced (`_record_checkin`). These are exactly the Sunday
  phone-mismatch cases.

Together: server-side catches the silent check-in failures; client-side catches
the visible popup/banner errors on both surfaces. Nothing slips through, and no
duplicate rows are produced (each surface has exactly one capture path).

## 3. Data Model — new table `intake_issues`

Created idempotently in `app/rag/db_init.py` (raw `CREATE TABLE IF NOT EXISTS`),
matching the existing `chat_logs` / `kb_entries` pattern (Alembic is not used for
these runtime tables). SQLAlchemy model added to `app/db/models.py`.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | default uuid4 |
| `kind` | Text | `checkin` \| `registration` |
| `reason` | Text | short code: `phone_not_registered`, `connect_mismatch`, `phone_exists`, `validation_error`, `schema_error`, `server_error`, `ui_error` |
| `message` | Text | the exact text the user saw (bot reply or banner text) |
| `source` | Text | `client` \| `server` |
| `http_status` | Integer | nullable — set for client-reported errors (e.g. 409, 422, 500) |
| `phone` | Text | nullable — pulled out for lookup |
| `email` | Text | nullable — pulled out for lookup |
| `name` | Text | nullable — pulled out for display |
| `details` | JSONB | full submitted payload / context |
| `session_id` | Text | nullable — chat session for check-in |
| `created_at` | TimestampTZ | server default now() |
| `resolved_at` | TimestampTZ | nullable — set by the "Mark handled" action |

`message` is length-capped (a few thousand chars) at the capture boundary.

## 4. Capture Mechanisms (defensive — never break the visitor's flow)

New module `app/services/intake/logs.py`, following the `log_chat` defensive
pattern (swallow all logging errors; never raise into the request path):

- `log_checkin_failure(session_id, reason, message, phone, service_type, connect_name)`
  — called at the two failure `return`s in
  `app/services/checkin/check_in.py::_record_checkin`. `_record_checkin` gains a
  `session_id` parameter (threaded from `handle_checkin`) so the row can carry it.
- `report_intake_issue(kind, message, http_status, details, session_id)`
  — inserts a row from a client report. The client stays "dumb" (it only knows the
  displayed text + status); the **`reason` is derived server-side** from
  `http_status` so codes stay consistent with the backend: `409`→`phone_exists`
  (registration), `422`→`validation_error`, `>=500`→`server_error`, otherwise
  `ui_error`. `phone`/`email`/`name` are pulled out of `details` when present.
- `get_intake_issues(db, kind="all", q=None, limit=100)` — newest-first, optional
  `kind` filter and keyword `q` matched against `phone`/`email`/`name`/`message`.
- `mark_intake_resolved(db, issue_id)` — stamps `resolved_at`.

**Session isolation:** the server-side check-in logger and the client-report
endpoint each open their **own** `SessionLocal`. This matters because a failed
registration leaves the request's DB session in an aborted transaction; logging
must not depend on it.

## 5. Backend API

- `POST /api/intake-issues/report` — **public** (unauthenticated visitors call
  it). Body: `{ kind, message, http_status?, details?, session_id? }` (`reason`
  is derived server-side; `phone`/`email`/`name` are read from `details`). Inserts
  one row via `report_intake_issue`. Caps `message`/field lengths; ignores
  malformed input gracefully (best-effort — a report failure must never surface to
  the visitor). Low abuse value (insert-only into an admin-viewable table); noted
  as a small tradeoff.
- `GET /api/admin/intake-issues?kind=all|checkin|registration&q=<keyword>&limit=`
  — admin-gated via the existing `require_admin`. Returns rows (newest first).
- `PATCH /api/admin/intake-issues/{id}/resolve` — admin-gated; calls
  `mark_intake_resolved`.

Registered on the existing routers: the public report route in a small new
`app/api/intake.py` (mounted under `/api`), the admin routes added to
`app/api/admin.py`.

## 6. Client-side Reporter (frontend)

A small shared helper `frontend/lib/reportIssue.ts` (or colocated util):
`reportIssue({ kind, message, httpStatus?, details?, sessionId? })` that POSTs to
`/api/intake-issues/report` and never throws (best-effort; a reporting failure is
swallowed).

Wired in at the exact points where the app shows an error to the user:

- **Registration** (`frontend/app/register/page.tsx`): in the `catch` block that
  sets the red `notice`, call `reportIssue` with `kind: "registration"`, the exact
  `message` shown, the HTTP status, and the submitted form (name/email/phone/…) as
  `details`. This captures phone_exists, 422 validation, 500 "code-like" errors,
  and network/proxy errors — whatever the banner displays.
- **Chat widget** (`frontend/components/ChatWidget.tsx`): wherever an error state
  is shown to the user (network / rate-limit), call `reportIssue` with
  `kind: "checkin"`, the shown message, status, and `sessionId`. (Normal bot
  check-in dead-ends are NOT reported here — those are captured server-side.)

Only real error displays trigger a report — never a success path.

## 7. Admin UI — third tab

Add a **"Check-in & registration issues"** tab to `frontend/app/admin/page.tsx`,
reusing the existing page structure and auth (`X-Admin-Key` from `sessionStorage`):

- Filter chips: **all / check-in / registration**; a search box (matches
  phone/email/name/message).
- Each row shows: `kind` badge, `reason`, `source` (client/server) and
  `http_status` when present, the exact `message`, the input details
  (phone/email/name), timestamp, and a **resolved** badge when handled.
- Row action **"Mark handled"** → `PATCH /api/admin/intake-issues/{id}/resolve`,
  mirroring the chat "resolved" workflow.

## 8. Privacy & Error Handling

- Rows contain member PII (names, emails, phones) — same sensitivity as the
  `members` table, and the viewer is admin-gated behind the shared password.
- All capture paths are wrapped so a logging/reporting failure never surfaces to
  the visitor or breaks registration/check-in.
- Stale Neon connections: server-side loggers open fresh sessions; the app's
  existing connection handling applies.

## 9. Testing

- **Unit:** `log_checkin_failure` / `report_intake_issue` build correct rows and
  reason codes; `get_intake_issues` filters by kind + keyword; `mark_intake_resolved`
  stamps `resolved_at`. Admin endpoints reject missing/wrong `X-Admin-Key`.
- **Integration:** `POST /api/intake-issues/report` inserts a row; a check-in with
  an unregistered phone produces a `phone_not_registered` row via the server path.
- **Manual:** reproduce (a) a duplicate-phone registration → red banner → row
  appears with `kind=registration`, `reason=phone_exists`, the exact banner text,
  and the submitted form; (b) an unregistered-phone check-in → row appears with
  `kind=checkin`, `reason=phone_not_registered`, the phone typed. Mark each handled
  and confirm the badge.

## 10. Out of Scope (deferred)

- Slack forwarding (design keeps the capture path reusable so a Slack webhook can
  be added later behind an env var).
- Any change to user-facing messages or the registration/check-in flows
  (e.g. "you're already registered — please check in"): a separate follow-up.
- Per-user admin accounts (single shared password remains, per the chat-history
  work).
