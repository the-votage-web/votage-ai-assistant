# Church AI Assistant

FastAPI + Next.js app for church check-ins, registrations, and FAQ assistance powered by AWS Bedrock.

**Stack**
- Backend: FastAPI, SQLAlchemy, Alembic, PostgreSQL
- Frontend: Next.js (App Router), React
- RAG: Postgres-backed document store
- LLM: AWS Bedrock (via `langchain_aws`)

**Repo Layout**
- `backend/`: FastAPI service and DB migrations
- `frontend/`: Next.js UI (chat widget + registration flow)

**Quick Start**
1. Configure backend environment in `backend/.env`.
1. Run PostgreSQL and create a database.
1. Run Alembic migrations.
1. Start the backend and frontend.

**Backend Setup**
1. `cd backend`
1. `python -m venv .venv`
1. `source .venv/bin/activate`
1. `pip install -r requirements.txt`
1. `alembic upgrade head`
1. `uvicorn app.main:app --reload --port 8000`

**Frontend Setup**
1. `cd frontend`
1. `npm install`
1. `npm run dev`

The frontend expects the backend on `http://localhost:8000` by default.

**Environment Variables**
Backend (`backend/.env`):
- `DATABASE_URL` (required)  
  Example: `postgresql+psycopg2://user:pass@localhost:5432/church_ai`
- `AWS_REGION` (required for Bedrock)
- `BEDROCK_MODEL_ID` or `BEDROCK_PROFILE_ARN` (required for Bedrock)
- `BEDROCK_PROVIDER` (optional, default `anthropic`)
- `BEDROCK_THROTTLE_COOLDOWN_SECONDS` (optional)
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (required for Bedrock auth)
- `AWS_BEARER_TOKEN_BEDROCK` (optional, if using bearer token auth)
- `OLLAMA_BASE_URL`, `LLM_MODEL`, `EMBED_MODEL` (present but currently unused in the Bedrock flow)
- `FRONTEND_URL`, `REGISTRATION_PAGE_URL`, `CORS_ORIGINS`
- `SUNDAY_CODE` (optional; enables simple check-in code verification)
- `AUTO_CREATE_TABLES` (optional; defaults to `false`)

Frontend (`frontend/.env.local`):
- `NEXT_PUBLIC_API_BASE` (required)  
  Example: `http://localhost:8000`

**API Endpoints**
- `POST /api/chat`  
  Body: `{ "session_id": "uuid", "message": "text" }`  
  Response: `{ "reply": "text" }`
- `GET /api/register/options`  
  Response: `{ "service_types": [...], "connect_groups": [...] }`
- `POST /api/register`  
  Body: `{ "phone_number", "first_name", "last_name", "email", "first_timer", "gender", "marital_status", "service_type", "connect_name" }`
- `POST /api/services`  
  Body: `{ "name", "theme?", "location?" }`
- `POST /api/connect-groups`  
  Body: `{ "service_id", "name", "description", "meeting_time", "meeting_day" }`

**Tests**
- `cd backend`
- `python -m unittest`

**Notes**
- Alembic reads `DATABASE_URL` from `backend/.env`.
- The RAG store is backed by PostgreSQL and creates the `rag_documents` table on first use.
- CORS is driven by `CORS_ORIGINS` (comma-separated list).
