from pydantic import BaseModel, Field
from typing import Literal, Optional

Intent = Literal[
    "checkin",
    "first_timer",
    "faq",
    "update_profile",
    "unknown"
]

class Extracted(BaseModel):
    intent: Intent = Field(..., description="User intent.")
    phone: Optional[str] = Field(None, description="Phone if provided.")
    full_name: Optional[str] = Field(None, description="Name if provided.")
    sunday_code: Optional[str] = Field(None, description="Rotating attendance code if provided.")
    question: Optional[str] = Field(None, description="FAQ question if intent=faq")
    service_type: Optional[Literal["sunday_service", "connect", "special_service"]] = Field(
        None, description="Service type for check-in if provided."
    )
