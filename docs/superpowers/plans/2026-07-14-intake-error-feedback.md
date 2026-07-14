# Check-in & Registration Error Feedback — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture every failed registration and check-in (the user's input + the exact error shown) into a new `intake_issues` table, viewable and markable-as-handled in a new admin tab — bundled with the admin chat-history work in one PR.

**Architecture:** Visible popup/banner errors are reported by the **frontend** (exact on-screen text, any origin) to a public `POST /api/intake-issues/report`. Silent check-in dead-ends (unrecognized phone, connect mismatch) are logged **server-side** in `_record_checkin`. Both write to `intake_issues`. A new admin tab lists them (filter by kind, search phone/email/name/message) with a "Mark handled" action.

**Tech Stack:** FastAPI + SQLAlchemy + psycopg2, Postgres/pgvector on Neon, Next.js App Router + React + TypeScript.

## Global Constraints

- Runtime tables are created by raw SQL in `app/rag/db_init.py` (`CREATE TABLE IF NOT EXISTS`) at startup — NOT Alembic. New tables go there (matches `chat_logs`/`kb_entries`).
- Admin endpoints MUST use the existing `require_admin` dependency in `app/api/admin.py` (`X-Admin-Key` vs `settings.ADMIN_API_KEY`, deny-by-default).
- All capture paths are **defensive**: a logging/reporting failure must never raise into the visitor's request or the frontend UX (mirror `app/services/faq/logs.py::log_chat`).
- Server-side loggers open their **own** `SessionLocal` (a failed registration leaves the request session in an aborted transaction).
- `reason` for client-reported errors is derived **server-side** from `http_status`: `409`→`phone_exists` (registration), `422`→`validation_error`, `>=500`→`server_error`, else `ui_error`. Server-side check-in failures set precise reasons directly (`phone_not_registered`, `connect_mismatch`).
- `intake_issues.details` is stored as a **JSON string in a TEXT column** (consistent with the ORM Text mapping; no JSONB casting).
- The ChatWidget is reused for both FAQ chat and check-in — only report from it when `apiUrl.includes("checkin")`.
- `message` and extracted fields are length-capped (`MAX_MESSAGE_LEN = 4000`).
- Tests requiring DB assume `.env` + Neon reachable (VPN off); pure-logic tests need no network. Run tests with the venv: `backend/.venv/Scripts/python.exe -m unittest` and `PYTHONUTF8=1`.

---

## File Structure

**Backend**
- Modify `app/db/models.py` — add `IntakeIssue` model; add `Integer` to the imports.
- Modify `app/rag/db_init.py` — `CREATE TABLE IF NOT EXISTS intake_issues`.
- Create `app/services/intake/__init__.py` — empty package marker.
- Create `app/services/intake/logs.py` — `derive_reason` (pure), `report_intake_issue`, `log_checkin_failure`, `get_intake_issues`, `mark_intake_resolved`.
- Modify `app/services/checkin/check_in.py` — thread `session_id` into `_record_checkin`; log the two failure returns.
- Create `app/api/intake.py` — public `POST /api/intake-issues/report`.
- Modify `app/api/admin.py` — `GET /admin/intake-issues`, `PATCH /admin/intake-issues/{id}/resolve`.
- Modify `app/main.py` — register the intake router.

**Backend tests**
- Create `backend/tests/test_intake.py` — `derive_reason` pure tests + admin auth-gate + report endpoint insert.

**Frontend**
- Create `frontend/lib/reportIssue.ts` — best-effort client reporter.
- Modify `frontend/app/register/page.tsx` — report on the error banner.
- Modify `frontend/components/ChatWidget.tsx` — report check-in widget errors.
- Modify `frontend/app/admin/page.tsx` — third "Check-in & registration issues" tab.

**Docs**
- Modify `CHANGE_LOG.md`.

---

## Task 1: Database schema (`IntakeIssue` model + startup DDL)

**Files:**
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/rag/db_init.py`

**Interfaces:**
- Produces: `IntakeIssue` ORM model and runtime table `intake_issues`.

- [ ] **Step 1: Add `Integer` to the imports in `models.py`**

Change the SQLAlchemy import line at the top of `backend/app/db/models.py`:

```python
from sqlalchemy import String, Date, DateTime, ForeignKey, UniqueConstraint, func, Text, Boolean, Float, Integer
```

- [ ] **Step 2: Add the `IntakeIssue` model at the end of `models.py`**

```python
class IntakeIssue(Base):
    """A failed registration or check-in, captured for admin review.
    kind=checkin|registration; source=client|server."""
    __tablename__ = "intake_issues"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(10), nullable=False, default="server")
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 3: Add startup DDL in `db_init.py`**

In `backend/app/rag/db_init.py`, inside `setup()` just before `self.conn.commit()`:

```python
            # Failed registrations / check-ins captured for admin review
            cur.execute("""
                CREATE TABLE IF NOT EXISTS intake_issues (
                    id UUID PRIMARY KEY,
                    kind TEXT NOT NULL,
                    reason TEXT,
                    message TEXT,
                    source TEXT NOT NULL DEFAULT 'server',
                    http_status INTEGER,
                    phone TEXT,
                    email TEXT,
                    name TEXT,
                    details TEXT,
                    session_id TEXT,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    resolved_at TIMESTAMPTZ
                );
            """)
```

- [ ] **Step 4: Verify model + DDL**

Run: `cd backend && ./.venv/Scripts/python.exe -c "from app.db.models import IntakeIssue; print('intake_issues', IntakeIssue.__tablename__, 'source' in IntakeIssue.__table__.columns)"`
Expected: `intake_issues intake_issues True`

Run: `cd backend && PYTHONUTF8=1 ./.venv/Scripts/python.exe -c "from app.db.config import settings; from app.rag.db_init import DBInitializer; DBInitializer(settings.DATABASE_URL).setup()"`
Expected: prints `✅ pgvector DB initialized` (idempotent).

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/models.py backend/app/rag/db_init.py
git commit -m "feat(intake): add intake_issues table for captured failures"
```

---

## Task 2: Intake service (reason derivation + capture/query functions)

**Files:**
- Create: `backend/app/services/intake/__init__.py`
- Create: `backend/app/services/intake/logs.py`
- Test: `backend/tests/test_intake.py`

**Interfaces:**
- Produces:
  - `derive_reason(kind: str, http_status: Optional[int]) -> str`
  - `report_intake_issue(kind, message, http_status=None, details=None, session_id=None) -> None`
  - `log_checkin_failure(session_id, reason, message, phone, service_type=None, connect_name=None) -> None`
  - `get_intake_issues(db, kind="all", q=None, limit=100) -> list[dict]`
  - `mark_intake_resolved(db, issue_id) -> bool`

- [ ] **Step 1: Write the failing pure-logic test**

Create `backend/tests/test_intake.py`:

```python
import unittest
from app.services.intake.logs import derive_reason


class TestDeriveReason(unittest.TestCase):
    def test_registration_conflict_is_phone_exists(self):
        self.assertEqual(derive_reason("registration", 409), "phone_exists")

    def test_validation(self):
        self.assertEqual(derive_reason("registration", 422), "validation_error")

    def test_server_error(self):
        self.assertEqual(derive_reason("checkin", 500), "server_error")
        self.assertEqual(derive_reason("checkin", 502), "server_error")

    def test_default_ui_error(self):
        self.assertEqual(derive_reason("registration", None), "ui_error")
        self.assertEqual(derive_reason("checkin", 400), "ui_error")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it (expect failure)**

Run: `cd backend && ./.venv/Scripts/python.exe -m unittest tests.test_intake -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.intake'`

- [ ] **Step 3: Create the package marker**

Create `backend/app/services/intake/__init__.py` (empty file).

- [ ] **Step 4: Implement `logs.py`**

Create `backend/app/services/intake/logs.py`:

```python
"""Capture failed registrations and check-ins for admin review.

Defensive: logging must never break the visitor's flow (mirrors faq/logs.py).
The pure helper derive_reason is import-safe for unit testing.
"""
import uuid
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import IntakeIssue

MAX_MESSAGE_LEN = 4000


def derive_reason(kind: str, http_status: Optional[int]) -> str:
    """Map an HTTP status to a stable reason code for client-reported errors."""
    if http_status == 409:
        return "phone_exists" if kind == "registration" else "duplicate"
    if http_status == 422:
        return "validation_error"
    if http_status is not None and http_status >= 500:
        return "server_error"
    return "ui_error"


def _clip(text: Optional[str]) -> Optional[str]:
    return text[:MAX_MESSAGE_LEN] if text else text


def _full_name(details: Dict[str, Any]) -> Optional[str]:
    first = str(details.get("first_name") or "").strip()
    last = str(details.get("last_name") or "").strip()
    full = f"{first} {last}".strip()
    return full or None


def _insert(db: Session, **fields) -> None:
    db.add(IntakeIssue(id=uuid.uuid4(), **fields))
    db.commit()


def report_intake_issue(kind: str, message: str, http_status: Optional[int] = None,
                        details: Optional[Dict[str, Any]] = None,
                        session_id: Optional[str] = None) -> None:
    """Insert a client-reported UI error. Own session; never raises."""
    details = details or {}
    kind = kind if kind in ("checkin", "registration") else "registration"
    try:
        db = SessionLocal()
        try:
            _insert(
                db,
                kind=kind,
                reason=derive_reason(kind, http_status),
                message=_clip(message),
                source="client",
                http_status=http_status,
                phone=_clip(details.get("phone_number") or details.get("phone")),
                email=_clip(details.get("email")),
                name=_clip(_full_name(details)),
                details=_clip(json.dumps(details)),
                session_id=session_id,
            )
        finally:
            db.close()
    except Exception as exc:
        print(f"report_intake_issue failed: {exc!r}")


def log_checkin_failure(session_id: Optional[str], reason: str, message: str,
                        phone: Optional[str], service_type: Optional[str] = None,
                        connect_name: Optional[str] = None) -> None:
    """Insert a server-side check-in dead-end. Own session; never raises."""
    try:
        db = SessionLocal()
        try:
            _insert(
                db,
                kind="checkin",
                reason=reason,
                message=_clip(message),
                source="server",
                http_status=None,
                phone=_clip(phone),
                email=None,
                name=None,
                details=json.dumps({"phone": phone, "service_type": service_type, "connect_name": connect_name}),
                session_id=session_id,
            )
        finally:
            db.close()
    except Exception as exc:
        print(f"log_checkin_failure failed: {exc!r}")


def _to_dict(r: IntakeIssue) -> Dict:
    return {
        "id": str(r.id),
        "kind": r.kind,
        "reason": r.reason,
        "message": r.message,
        "source": r.source,
        "http_status": r.http_status,
        "phone": r.phone,
        "email": r.email,
        "name": r.name,
        "session_id": r.session_id,
        "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def get_intake_issues(db: Session, kind: str = "all", q: Optional[str] = None,
                      limit: int = 100) -> List[Dict]:
    query = db.query(IntakeIssue)
    if kind in ("checkin", "registration"):
        query = query.filter(IntakeIssue.kind == kind)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            IntakeIssue.phone.ilike(like),
            IntakeIssue.email.ilike(like),
            IntakeIssue.name.ilike(like),
            IntakeIssue.message.ilike(like),
        ))
    rows = query.order_by(IntakeIssue.created_at.desc()).limit(limit).all()
    return [_to_dict(r) for r in rows]


def mark_intake_resolved(db: Session, issue_id: str) -> bool:
    try:
        row = db.query(IntakeIssue).filter(IntakeIssue.id == issue_id).first()
        if not row:
            return False
        row.resolved_at = datetime.now(timezone.utc)
        db.commit()
        return True
    except Exception as exc:
        db.rollback()
        print(f"mark_intake_resolved failed: {exc!r}")
        return False
```

- [ ] **Step 5: Run the pure test (expect pass)**

Run: `cd backend && ./.venv/Scripts/python.exe -m unittest tests.test_intake -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/intake/ backend/tests/test_intake.py
git commit -m "feat(intake): capture/query service + reason derivation"
```

---

## Task 3: Server-side check-in failure capture

**Files:**
- Modify: `backend/app/services/checkin/check_in.py`

**Interfaces:**
- Consumes: `log_checkin_failure` (Task 2).
- Changes: `_record_checkin(db, phone, service_type, connect_name=None, session_id=None)` gains `session_id`; logs at its two failure returns.

- [ ] **Step 1: Import the logger**

At the top of `backend/app/services/checkin/check_in.py`, add:

```python
from app.services.intake.logs import log_checkin_failure
```

- [ ] **Step 2: Add `session_id` to `_record_checkin` and log the failures**

Change the signature:

```python
def _record_checkin(db: Session, phone: str, service_type: str, connect_name: Optional[str] = None, session_id: Optional[str] = None) -> str:
```

Replace the "phone not recognized" return:

```python
    member = find_member_by_phone(db, phone)
    if not member:
        message = (
            "👋 I don’t recognize that phone number yet.\n"
            f"Please register here first: {settings.REGISTRATION_PAGE_URL}"
        )
        log_checkin_failure(session_id, "phone_not_registered", message, phone, service_type, connect_name)
        return message
```

Replace the connect-mismatch return:

```python
        if registered_connect and selected_connect and registered_connect.lower() != selected_connect.lower():
            message = (
                "❌ Connect check-in failed. "
                f"Your registration is under {registered_connect}. "
                f"You selected {selected_connect}. "
                "Please select your registered connect group or contact an admin to update your profile.\n\n"
                f"{connect._connect_group_prompt()}"
            )
            log_checkin_failure(session_id, "connect_mismatch", message, phone, service_type, connect_name)
            return message
```

- [ ] **Step 3: Pass `session_id` at all `_record_checkin` call sites**

In `handle_checkin`, add `session_id=session_id` to every `_record_checkin(...)` call (there are four: the connect and non-connect branches inside the "continue existing flow" block, and the same two inside the "start new flow" block). Example:

```python
            response = _record_checkin(db, pending_phone, "connect", connect_name=chosen_connect_name, session_id=session_id)
```
```python
        response = _record_checkin(db, pending_phone, chosen_service_type, session_id=session_id)
```
```python
            response = _record_checkin(db, phone, "connect", connect_name=chosen_connect_name, session_id=session_id)
```
```python
        response = _record_checkin(db, phone, service_type, session_id=session_id)
```

- [ ] **Step 4: Verify it imports and a failed check-in logs a row**

Run: `cd backend && PYTHONUTF8=1 ./.venv/Scripts/python.exe -c "
from app.db.session import SessionLocal
from app.services.checkin.check_in import handle_checkin
from app.services.intake.logs import get_intake_issues
db = SessionLocal()
reply = handle_checkin(db, 'plan-test-session', '08000000000 sunday_service')
print('REPLY:', reply[:40])
rows = get_intake_issues(db, kind='checkin', q='08000000000')
print('logged rows:', len(rows), rows[0]['reason'] if rows else None)
# cleanup
import psycopg2; from app.db.config import settings
c = psycopg2.connect(settings.DATABASE_URL); cur = c.cursor()
cur.execute(\"DELETE FROM intake_issues WHERE phone = '08000000000'\"); c.commit(); c.close()
db.close()
print('cleaned up')
"`
Expected: `REPLY:` starts with the "don't recognize" text; `logged rows: 1 phone_not_registered`; `cleaned up`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/checkin/check_in.py
git commit -m "feat(intake): log check-in dead-ends (unrecognized phone, connect mismatch)"
```

---

## Task 4: Public report endpoint + wiring

**Files:**
- Create: `backend/app/api/intake.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces route (under `/api`): `POST /intake-issues/report`.

- [ ] **Step 1: Create the router**

Create `backend/app/api/intake.py`:

```python
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.services.intake.logs import report_intake_issue

router = APIRouter()


class IssueReportIn(BaseModel):
    kind: str
    message: str
    http_status: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None


@router.post("/intake-issues/report")
def report_issue(payload: IssueReportIn):
    """Public: the frontend reports the exact error a visitor saw. Best-effort."""
    report_intake_issue(
        kind=payload.kind,
        message=payload.message,
        http_status=payload.http_status,
        details=payload.details,
        session_id=payload.session_id,
    )
    return {"ok": True}
```

- [ ] **Step 2: Register the router in `main.py`**

Add the import with the others:

```python
from app.api.intake import router as intake_router
```

And after the existing `include_router` calls:

```python
app.include_router(intake_router, prefix="/api")
```

- [ ] **Step 3: Verify the endpoint inserts a row**

Run: `cd backend && PYTHONUTF8=1 ./.venv/Scripts/python.exe -c "
from app.db import config
config.settings.ADMIN_API_KEY = 'k'
from app.main import app
from fastapi.testclient import TestClient
c = TestClient(app)
r = c.post('/api/intake-issues/report', json={'kind':'registration','message':'This phone number is already registered.','http_status':409,'details':{'phone_number':'0811PLANTEST','email':'x@y.z','first_name':'A','last_name':'B'}})
print('report status', r.status_code, r.json())
from app.db.session import SessionLocal
from app.services.intake.logs import get_intake_issues
db = SessionLocal(); rows = get_intake_issues(db, q='0811PLANTEST')
print('row:', rows[0]['reason'], rows[0]['kind'], rows[0]['source'], rows[0]['name'])
import psycopg2; from app.db.config import settings
cc = psycopg2.connect(settings.DATABASE_URL); cur = cc.cursor(); cur.execute(\"DELETE FROM intake_issues WHERE phone = '0811PLANTEST'\"); cc.commit(); cc.close(); db.close()
print('cleaned up')
" 2>&1 | grep -v -E "on_event|Deprecat|Read more|FastAPI|Lifespan|return self"`
Expected: `report status 200 {'ok': True}`; `row: phone_exists registration client A B`; `cleaned up`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/intake.py backend/app/main.py
git commit -m "feat(intake): public report endpoint for client-side error capture"
```

---

## Task 5: Admin endpoints (list + resolve)

**Files:**
- Modify: `backend/app/api/admin.py`
- Test: `backend/tests/test_intake.py` (extend)

**Interfaces:**
- Produces (admin-gated): `GET /admin/intake-issues`, `PATCH /admin/intake-issues/{id}/resolve`.

- [ ] **Step 1: Add the imports and endpoints to `admin.py`**

Add to the imports:

```python
from app.services.intake.logs import get_intake_issues, mark_intake_resolved
```

Add the endpoints (after the existing admin routes):

```python
@router.get("/admin/intake-issues")
def admin_intake_issues(kind: str = "all", q: Optional[str] = None, limit: int = 100,
                        db: Session = Depends(get_db), _admin: None = Depends(require_admin)):
    limit = max(1, min(limit, 500))
    return get_intake_issues(db, kind=kind, q=q, limit=limit)


@router.patch("/admin/intake-issues/{issue_id}/resolve")
def admin_intake_resolve(issue_id: str, db: Session = Depends(get_db), _admin: None = Depends(require_admin)):
    ok = mark_intake_resolved(db, issue_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Issue not found.")
    return {"ok": True}
```

- [ ] **Step 2: Add auth-gate tests**

Append to `backend/tests/test_intake.py`:

```python
class TestIntakeAdminAuth(unittest.TestCase):
    def _client(self, key="secret-key"):
        from app.db import config
        config.settings.ADMIN_API_KEY = key
        from app.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_list_requires_admin(self):
        resp = self._client().get("/api/admin/intake-issues")
        self.assertEqual(resp.status_code, 403)

    def test_list_ok_with_key(self):
        resp = self._client().get("/api/admin/intake-issues",
                                  headers={"X-Admin-Key": "secret-key"})
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_resolve_missing_is_404(self):
        resp = self._client().patch(
            "/api/admin/intake-issues/00000000-0000-0000-0000-000000000000/resolve",
            headers={"X-Admin-Key": "secret-key"})
        self.assertEqual(resp.status_code, 404)
```

- [ ] **Step 3: Run intake tests**

Run: `cd backend && PYTHONUTF8=1 ./.venv/Scripts/python.exe -m unittest tests.test_intake 2>&1 | grep -E "Ran|OK|FAILED"`
Expected: `OK` (7 tests).

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/admin.py backend/tests/test_intake.py
git commit -m "feat(intake): admin endpoints to list and resolve captured issues"
```

---

## Task 6: Frontend client reporter

**Files:**
- Create: `frontend/lib/reportIssue.ts`

**Interfaces:**
- Produces: `reportIssue({ kind, message, httpStatus?, details?, sessionId? }): Promise<void>` — best-effort, never throws.

- [ ] **Step 1: Create the reporter**

Create `frontend/lib/reportIssue.ts`:

```ts
type ReportArgs = {
  kind: "registration" | "checkin";
  message: string;
  httpStatus?: number;
  details?: Record<string, unknown>;
  sessionId?: string;
};

/** Best-effort: report the exact error the user saw. Never throws. */
export async function reportIssue(args: ReportArgs): Promise<void> {
  try {
    const base = process.env.NEXT_PUBLIC_API_BASE || "";
    const url = base ? `${base}/api/intake-issues/report` : "/api/intake-issues/report";
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: args.kind,
        message: args.message,
        http_status: args.httpStatus ?? null,
        details: args.details ?? null,
        session_id: args.sessionId ?? null,
      }),
      keepalive: true,
    });
  } catch {
    // best-effort; never disrupt the user
  }
}
```

- [ ] **Step 2: Lint**

Run: `cd frontend && npx --no-install eslint lib/reportIssue.ts`
Expected: exit 0, no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/reportIssue.ts
git commit -m "feat(intake): best-effort client error reporter"
```

---

## Task 7: Wire the reporter into the registration form and chat widget

**Files:**
- Modify: `frontend/app/register/page.tsx`
- Modify: `frontend/components/ChatWidget.tsx`

**Interfaces:**
- Consumes: `reportIssue` (Task 6).

- [ ] **Step 1: Registration form — capture status and report on error**

In `frontend/app/register/page.tsx`, add the import:

```tsx
import { reportIssue } from "@/lib/reportIssue";
```

In `onSubmit`, capture the HTTP status and report in the `catch`. Change the `try` to track status and the `catch` to report. Replace the existing `try { ... } catch (err) { ... }` body so it reads:

```tsx
    let httpStatus: number | undefined;
    try {
      const normalizedPhone = phoneNumber.startsWith("+") ? phoneNumber : `+${phoneNumber}`;
      const payload = {
        first_name: firstName,
        last_name: lastName,
        email,
        phone_number: normalizedPhone,
        gender,
        marital_status: maritalStatus,
        service_type: serviceType,
        connect_name: showConnect ? connectName : null,
      };

      const url = base ? `${base}/api/register` : "/api/register";
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      httpStatus = res.status;

      if (!res.ok) {
        let message = "Registration failed. Please try again.";
        try {
          const body = (await res.json()) as { detail?: string; message?: string };
          message = body.detail || body.message || message;
        } catch {
          // Ignore JSON parsing errors and keep default message.
        }
        throw new Error(message);
      }

      const data = (await res.json()) as { ok: boolean; message: string };
      setFirstName("");
      setLastName("");
      setEmail("");
      setPhoneNumber("");
      setGender("male");
      setMaritalStatus("single");
      setServiceType("sunday_service");
      setConnectName(connectOptions[0] ?? DEFAULT_CONNECT_OPTIONS[0]);
      setNotice({
        type: "success",
        text: `${data.message} Redirecting...`,
      });
      setTimeout(() => router.push("/"), 1200);
    } catch (err) {
      const text = err instanceof Error ? err.message : "Registration failed";
      setNotice({ type: "error", text });
      void reportIssue({
        kind: "registration",
        message: text,
        httpStatus,
        details: {
          first_name: firstName,
          last_name: lastName,
          email,
          phone_number: phoneNumber,
          gender,
          marital_status: maritalStatus,
          service_type: serviceType,
          connect_name: showConnect ? connectName : null,
        },
      });
    } finally {
      setBusy(false);
    }
```

(This preserves the existing behaviour; it only adds `httpStatus` tracking and the `reportIssue` call. The `payload` variable is unchanged and still used for the request.)

- [ ] **Step 2: Chat widget — report check-in errors only**

In `frontend/components/ChatWidget.tsx`, add the import near the top:

```tsx
import { reportIssue } from "@/lib/reportIssue";
```

In `sendText`, extend the `catch (err)` block to report when this is the check-in widget:

```tsx
    } catch (err) {
      const busyMessage =
        "I’m receiving too many requests right now. Please try again in a minute.";
      const shown =
        err instanceof Error && err.message === "SERVICE_BUSY"
          ? busyMessage
          : "Sorry — I couldn’t reach the server. Please try again.";
      setMsgs((m) => [...m, { role: "ai", text: shown }]);
      if (apiUrl.includes("checkin")) {
        void reportIssue({
          kind: "checkin",
          message: shown,
          httpStatus: err instanceof Error && err.message === "SERVICE_BUSY" ? 503 : undefined,
          sessionId,
          details: { typed: text },
        });
      }
    } finally {
      setBusy(false);
    }
```

- [ ] **Step 3: Lint both files**

Run: `cd frontend && npx --no-install eslint app/register/page.tsx components/ChatWidget.tsx`
Expected: exit 0 (no new errors for these files).

- [ ] **Step 4: Commit**

```bash
git add frontend/app/register/page.tsx frontend/components/ChatWidget.tsx
git commit -m "feat(intake): report registration + check-in widget errors from the client"
```

---

## Task 8: Admin UI — third "Check-in & registration issues" tab

**Files:**
- Modify: `frontend/app/admin/page.tsx`

**Interfaces:**
- Consumes: `GET /api/admin/intake-issues`, `PATCH /api/admin/intake-issues/{id}/resolve`.

- [ ] **Step 1: Add the issues type, state, and tab**

In `frontend/app/admin/page.tsx`:

Add a type near the other types:

```tsx
type IntakeIssue = {
  id: string;
  kind: string;
  reason: string | null;
  message: string | null;
  source: string;
  http_status: number | null;
  phone: string | null;
  email: string | null;
  name: string | null;
  session_id: string | null;
  resolved_at: string | null;
  created_at: string | null;
};
type IssueKind = "all" | "checkin" | "registration";
```

Extend the tab state and add issues state (replace the `tab` useState line and add new state after `kb`):

```tsx
  const [tab, setTab] = useState<"logs" | "kb" | "issues">("logs");
```
```tsx
  const [issues, setIssues] = useState<IntakeIssue[]>([]);
  const [issueKind, setIssueKind] = useState<IssueKind>("all");
  const [issueSearch, setIssueSearch] = useState("");
```

- [ ] **Step 2: Load issues in the data effect**

Extend the existing data-loading `useEffect` to also handle the issues tab. Replace the effect body's async IIFE branch selection so it includes issues:

```tsx
    void (async () => {
      if (tab === "logs") {
        const params = new URLSearchParams({ status, limit: "200" });
        if (search.trim()) params.set("q", search.trim());
        const res = await fetch(`/api/admin/logs?${params.toString()}`, { headers: authHeaders() });
        if (cancelled) return;
        if (res.status === 403) { signOut(); return; }
        if (res.ok) setLogs(await res.json());
      } else if (tab === "kb") {
        const res = await fetch("/api/admin/kb", { headers: authHeaders() });
        if (cancelled) return;
        if (res.status === 403) { signOut(); return; }
        if (res.ok) setKb(await res.json());
      } else {
        const params = new URLSearchParams({ kind: issueKind, limit: "200" });
        if (issueSearch.trim()) params.set("q", issueSearch.trim());
        const res = await fetch(`/api/admin/intake-issues?${params.toString()}`, { headers: authHeaders() });
        if (cancelled) return;
        if (res.status === 403) { signOut(); return; }
        if (res.ok) setIssues(await res.json());
      }
    })();
```

Update the effect dependency array to include the issue filters:

```tsx
  }, [adminKey, tab, status, search, issueKind, issueSearch, refreshKey, authHeaders]);
```

- [ ] **Step 3: Add the resolve handler**

Add near `deleteEntry`:

```tsx
  async function resolveIssue(id: string) {
    const res = await fetch(`/api/admin/intake-issues/${id}/resolve`, { method: "PATCH", headers: authHeaders() });
    if (res.status === 403) return signOut();
    if (res.ok) refresh();
  }
```

- [ ] **Step 4: Add the tab button and the panel**

Add the third tab button in the `<nav className={styles.tabs}>` block:

```tsx
        <button className={tab === "issues" ? styles.tabActive : styles.tab} onClick={() => setTab("issues")}>Check-in & registration issues</button>
```

Add the panel after the `{tab === "kb" && ( ... )}` block:

```tsx
      {tab === "issues" && (
        <>
          <div className={styles.controls}>
            {(["all", "checkin", "registration"] as IssueKind[]).map((k) => (
              <button key={k} className={issueKind === k ? styles.chipActive : styles.chip} onClick={() => setIssueKind(k)}>
                {k}
              </button>
            ))}
            <input
              value={issueSearch}
              onChange={(e) => setIssueSearch(e.target.value)}
              placeholder="Search phone / email / name..."
              className={styles.search}
            />
          </div>
          <div className={styles.list}>
            {issues.map((it) => (
              <div key={it.id} className={styles.row}>
                <div className={styles.rowMain}>
                  <p className={styles.q}>
                    {it.kind} · {it.reason}
                    {it.http_status ? ` · HTTP ${it.http_status}` : ""} · {it.source}
                  </p>
                  <p className={styles.a}>{it.message}</p>
                  <div className={styles.meta}>
                    {it.name && <span className={styles.date}>{it.name}</span>}
                    {it.phone && <span className={styles.date}>📞 {it.phone}</span>}
                    {it.email && <span className={styles.date}>✉ {it.email}</span>}
                    {it.resolved_at && <span className={styles.badgeResolved}>handled</span>}
                    <span className={styles.date}>{it.created_at?.slice(0, 16).replace("T", " ")}</span>
                  </div>
                </div>
                {!it.resolved_at && (
                  <button className={styles.secondaryBtn} onClick={() => void resolveIssue(it.id)}>Mark handled</button>
                )}
              </div>
            ))}
            {issues.length === 0 && <p className={styles.empty}>No issues in this view yet.</p>}
          </div>
        </>
      )}
```

- [ ] **Step 5: Lint + type-check**

Run: `cd frontend && npx --no-install eslint app/admin/page.tsx && npx --no-install tsc --noEmit`
Expected: exit 0, no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/admin/page.tsx
git commit -m "feat(intake): admin tab to review and resolve check-in/registration issues"
```

---

## Task 9: End-to-end verification + changelog

**Files:**
- Modify: `CHANGE_LOG.md`

- [ ] **Step 1: Full backend test suite**

Run: `cd backend && PYTHONUTF8=1 ./.venv/Scripts/python.exe -m unittest tests.test_kb_helpers tests.test_admin_api tests.test_retriever_reconnect tests.test_intake 2>&1 | grep -E "Ran|OK|FAILED"`
Expected: `OK`.

- [ ] **Step 2: Manual end-to-end (servers running, admin at /admin)**

1. Register with a phone number that already exists → red banner appears → in the admin **Check-in & registration issues** tab, a `registration` / `phone_exists` row appears with the exact banner text and the submitted name/email/phone.
2. Check in with an unregistered phone number → in the tab, a `checkin` / `phone_not_registered` row appears with the phone typed.
3. Click **Mark handled** on a row → it shows the **handled** badge.
4. Use the kind filter and the search box (by phone/email) → results narrow correctly.

Expected: all four behave as described.

- [ ] **Step 3: Update the changelog**

Add a section to `CHANGE_LOG.md` documenting: the `intake_issues` table; client-side capture of visible/popup errors (registration + check-in widget) via `POST /api/intake-issues/report`; server-side capture of silent check-in dead-ends; the admin tab with filter/search and "Mark handled"; privacy note (member PII, admin-gated); Slack + message changes deferred.

- [ ] **Step 4: Commit**

```bash
git add CHANGE_LOG.md
git commit -m "docs(intake): changelog for check-in & registration error feedback"
```

---

## Self-Review Notes

- **Spec coverage:** §2 layered capture → Tasks 3 (server) + 6/7 (client); §3 data model → Task 1; §4 capture mechanisms → Tasks 2/3; §5 API → Tasks 4 (report) + 5 (admin); §6 client reporter → Tasks 6/7; §7 admin tab → Task 8; §8 privacy/defensive → Tasks 2 (own-session, swallow) + 4; §9 testing → Tasks 2/3/4/5/9. All covered.
- **Type consistency:** `report_intake_issue(kind, message, http_status, details, session_id)` and `log_checkin_failure(session_id, reason, message, phone, service_type, connect_name)` match their callers (Tasks 3, 4). Frontend `reportIssue` posts `http_status`/`session_id` (snake_case) matching `IssueReportIn` (Task 4). Reason codes (`phone_not_registered`, `connect_mismatch`, `phone_exists`, `validation_error`, `server_error`, `ui_error`) are consistent between `derive_reason`, the check-in logger, and the spec.
- **Defensive:** every capture path opens its own session and swallows exceptions; the registration/check-in flows are unchanged on the happy path (Task 7 only adds reporting in the existing error branches).
- **Reuse:** admin tab reuses the existing page styles/auth and the `refreshKey` pattern from the chat-history work; no new CSS needed.
