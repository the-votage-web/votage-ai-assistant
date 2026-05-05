from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.chat import router as chat_router
from app.api.form import router as form_router
from app.api.checkin import router as checkin_router
from app.api.connect import router as connect_router
from app.api.service import router as service_router
from app.db.config import settings
from app.db.session import engine
from app.db.models import Base

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")
app.include_router(form_router, prefix="/api")
app.include_router(checkin_router, prefix="/api")
app.include_router(connect_router, prefix="/api")
app.include_router(service_router, prefix="/api")


@app.get("/docs", include_in_schema=False)
def docs_landing() -> HTMLResponse:
    html = """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>API Docs</title>
        <style>
          body { font-family: system-ui, -apple-system, Segoe UI, sans-serif; margin: 40px; }
          .card { max-width: 720px; padding: 24px; border: 1px solid #e5e7eb; border-radius: 12px; }
          a { color: #2563eb; text-decoration: none; }
          a:hover { text-decoration: underline; }
          ul { padding-left: 18px; }
        </style>
      </head>
      <body>
        <div class="card">
          <h1>API Documentation</h1>
          <p>Choose a format:</p>
          <ul>
            <li><a href="/docs">Swagger UI</a></li>
            <li><a href="/redoc">ReDoc</a></li>
            <li><a href="/openapi.json">OpenAPI JSON</a></li>
          </ul>
        </div>
      </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.on_event("startup")
def create_tables_on_startup():
    # Keep disabled by default to avoid conflicts with Alembic migrations.
    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(bind=engine)
