from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.chat import router as chat_router
from app.api.form import router as form_router
from app.core.config import settings
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


@app.on_event("startup")
def create_tables_on_startup():
    # Keep disabled by default to avoid conflicts with Alembic migrations.
    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(bind=engine)
