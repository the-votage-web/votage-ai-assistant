from pydantic import BaseModel, field_validator
from uuid import UUID

SERVICE_KEYWORDS = {
    "sunday": "sunday_service",
    "sunday_service": "sunday_service",
    "connect": "connect",
    "special": "special_service",
    "special_service": "special_service",
}

DEFAULT_SERVICE_TYPES = ["sunday_service", "connect", "special_service"]

class ServiceCreateIn(BaseModel):
    name: str
    theme: str | None = None
    location: str | None = None

    @field_validator("name", "theme", "location", mode="before")
    @classmethod
    def _trim_optional_str(cls, value):
        if value is None:
            return None
        return value.strip() if isinstance(value, str) else value


class ServiceOut(BaseModel):
    id: UUID
    name: str
    theme: str | None = None
    location: str | None = None

