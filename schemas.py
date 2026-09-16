from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

ApplicationStatus = Literal["Applied", "Interview", "Offer", "Rejected"]
RequiredText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]


class ApplicationCreate(BaseModel):
    company: RequiredText
    position: RequiredText
    status: ApplicationStatus
    notes: str | None = Field(default=None, max_length=500)


class ApplicationUpdate(BaseModel):
    company: RequiredText | None = None
    position: RequiredText | None = None
    status: ApplicationStatus | None = None
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("company", "position", "status")
    @classmethod
    def reject_explicit_null(cls, value: str | None) -> str:
        # Omitted fields retain their defaults without running this validator.
        if value is None:
            raise ValueError("Field may be omitted, but must not be null")
        return value


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company: str
    position: str
    status: ApplicationStatus
    notes: str | None = None
    applied_at: datetime
