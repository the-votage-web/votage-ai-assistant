from pydantic import BaseModel, field_validator
from uuid import UUID

CONNECT_GROUP_ALIASES = {
    "kabod": "KABOD CONNECT",
    "newness": "NEWNESS CONNECT",
    "ugbowo": "UGBOWO CONNECT",
    "flourish": "FLOURISH CONNECT",
    "gatekeepers": "GATEKEEPERS CONNECT",
    "koinonia": "KOINONIA CONNECT",
    "koinoinia": "KOINONIA CONNECT",
    "ekehuan": "EKEHUAN CONNECT",
}

CONNECT_GROUPS = [
    "KABOD CONNECT",
    "NEWNESS CONNECT",
    "UGBOWO CONNECT",
    "FLOURISH CONNECT",
    "GATEKEEPERS CONNECT",
    "KOINONIA CONNECT",
    "EKEHUAN CONNECT",
]

class ConnectGroupCreateIn(BaseModel):
    service_id: UUID
    name: str
    description: str
    meeting_time: str
    meeting_day: str

    @field_validator("name", "description", "meeting_time", "meeting_day", mode="before")
    @classmethod
    def _trim_fields(cls, value):
        return value.strip() if isinstance(value, str) else value

class ConnectGroupOut(BaseModel):
    id: UUID
    service_id: UUID | None = None
    name: str
    description: str
    meeting_time: str
    meeting_day: str
