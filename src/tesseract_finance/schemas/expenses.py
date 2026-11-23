import datetime as dt
import uuid
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from tesseract_finance.schemas.money import Amount

Currency = Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{3}$", to_upper=True)]
Description = Annotated[str, Field(max_length=500)]


class ExpenseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Amount
    currency: Currency = "PLN"
    date: dt.date
    description: Description | None = None
    source_url: str | None = None
    is_planned: bool = False


class ExpenseUpdate(BaseModel):
    """Partial update: only fields present in the body change; null clears nullable ones."""

    model_config = ConfigDict(extra="forbid")

    amount: Amount | None = None
    currency: Currency | None = None
    date: dt.date | None = None
    description: Description | None = None
    source_url: str | None = None
    is_planned: bool | None = None

    @model_validator(mode="after")
    def reject_null_for_required_columns(self) -> Self:
        for name in ("amount", "currency", "date", "is_planned"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: Amount
    currency: str
    date: dt.date
    description: str | None
    source_url: str | None
    is_planned: bool
    created_at: dt.datetime
    updated_at: dt.datetime
