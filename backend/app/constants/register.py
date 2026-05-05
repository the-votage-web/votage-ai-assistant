from uuid import UUID
from pydantic import BaseModel, StrictStr, field_validator, model_validator
from app.constants.service import DEFAULT_SERVICE_TYPES


class RegistrationIn(BaseModel):
    phone_number: StrictStr
    first_name: str
    last_name: str
    email: StrictStr
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

    @field_validator("phone_number")
    @classmethod
    def _validate_phone_number(cls, value: str) -> str:
        v = value.strip()
        if v.startswith("+"):
            digits = v[1:]
        else:
            digits = v
        if not digits.isdigit():
            raise ValueError("phone_number must contain only digits (optionally prefixed by '+')")
        if len(digits) < 7 or len(digits) > 15:
            raise ValueError("phone_number must be between 7 and 15 digits")
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
