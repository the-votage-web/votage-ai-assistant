from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

DEFAULT_SERVICE_TYPES = ["sunday_service", "connect", "special_service"]
DEFAULT_CONNECT_GROUPS = [
    "KABOD CONNECT",
    "NEWNESS CONNECT",
    "UGBOWO CONNECT",
    "FLOURISH CONNECT",
    "GATEKEEPERS CONNECT",
    "KOINONIA CONNECT",
    "EKEHUAN CONNECT",
]


class RegistrationIn(BaseModel):
    phone_number: str
    first_name: str
    last_name: str
    email: str
    first_timer: bool = False
    gender: str
    marital_status: str
    service_type: str
    connect_name: str | None = None

    @field_validator(
        "phone_number",
        "first_name",
        "last_name",
        "email",
        "gender",
        "marital_status",
        "service_type",
        mode="before",
    )
    @classmethod
    def _trim_required(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("connect_name", mode="before")
    @classmethod
    def _trim_optional(cls, value):
        if value is None:
            return None
        return value.strip() if isinstance(value, str) else value

    @field_validator("gender")
    @classmethod
    def _validate_gender(cls, value: str) -> str:
        allowed = {"male", "female"}
        v = value.lower()
        if v not in allowed:
            raise ValueError(f"gender must be one of: {sorted(allowed)}")
        return v

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        v = value.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("email must be a valid email address")
        return v

    @field_validator("marital_status")
    @classmethod
    def _validate_marital_status(cls, value: str) -> str:
        allowed = {"single", "married", "divorced", "widowed"}
        v = value.lower()
        if v not in allowed:
            raise ValueError(f"marital_status must be one of: {sorted(allowed)}")
        return v

    @field_validator("service_type")
    @classmethod
    def _validate_service_type(cls, value: str) -> str:
        allowed = set(DEFAULT_SERVICE_TYPES)
        v = value.lower()
        if v not in allowed:
            raise ValueError(f"service_type must be one of: {sorted(allowed)}")
        return v

    @model_validator(mode="after")
    def _validate_connect_name(self):
        if self.service_type == "connect" and not self.connect_name:
            raise ValueError("connect_name is required when service_type is connect")
        if self.service_type != "connect":
            self.connect_name = None
        return self


class RegistrationOut(BaseModel):
    ok: bool
    message: str


class RegisterOptionsOut(BaseModel):
    service_types: list[str]
    connect_groups: list[str]


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
