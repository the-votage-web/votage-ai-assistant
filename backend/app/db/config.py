from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int = 5432
    DB_NAME: str
    DB_SSLMODE: str = ""
    DB_OPTIONS: str = ""
    DB_CHANNEL_BINDING: str = ""

    @property
    def DATABASE_URL(self) -> str:
        from sqlalchemy import URL
        query = {}
        if self.DB_SSLMODE:
            query["sslmode"] = self.DB_SSLMODE
        if self.DB_OPTIONS:
            query["options"] = self.DB_OPTIONS
        if self.DB_CHANNEL_BINDING:
            query["channel_binding"] = self.DB_CHANNEL_BINDING
            
        return URL.create(
            drivername="postgresql",
            username=self.DB_USER,
            password=self.DB_PASSWORD,
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_NAME,
            query=query if query else None
        ).render_as_string(hide_password=False)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "llama3.2"
    EMBED_MODEL: str = "nomic-embed-text"

    CHROMA_PATH: str = "./chroma"
    MEMBERS_COLLECTION: str = "members"
    DOCS_COLLECTION: str = "church_docs"

    FRONTEND_URL: str = "http://localhost:3000"
    REGISTRATION_PAGE_URL: str = "http://localhost:3000/register"
    SUNDAY_CODE: str = "change-me"  # set via env in production

    CORS_ORIGINS: str = "http://localhost:3000"
    AUTO_CREATE_TABLES: bool = False

    AWS_REGION: str = "us-east-1"
    OPENAI_API_KEY: str = ""
    OPENAI_EMBED_MODEL: str = "text-embedding-3-small"
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"
    OPENAI_CHECKIN_MODEL: str = "gpt-4o-mini"
    CHECKIN_LLM_PROVIDER: str = "bedrock"
    @model_validator(mode="after")
    def _normalize_urls(self):
        base = self.FRONTEND_URL.rstrip("/")
        if not self.REGISTRATION_PAGE_URL:
            self.REGISTRATION_PAGE_URL = f"{base}/register"
        elif "${FRONTEND_URL}" in self.REGISTRATION_PAGE_URL:
            self.REGISTRATION_PAGE_URL = self.REGISTRATION_PAGE_URL.replace("${FRONTEND_URL}", base)

        raw_cors = (self.CORS_ORIGINS or "").strip()
        if not raw_cors:
            self.CORS_ORIGINS = base
            return self

        normalized: list[str] = []
        for origin in raw_cors.split(","):
            value = origin.strip()
            if not value:
                continue
            if value == "${FRONTEND_URL}":
                value = base
            if not (value.startswith("http://") or value.startswith("https://")):
                raise ValueError(f"Invalid CORS origin '{value}'. Use http:// or https://")
            normalized.append(value.rstrip("/"))

        if not normalized:
            self.CORS_ORIGINS = base
        else:
            self.CORS_ORIGINS = ",".join(dict.fromkeys(normalized))
        return self

settings = Settings()
