import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import CHAR, CheckConstraint, ForeignKey, Index, Numeric, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from tesseract_finance.models.base import Base, Timestamps


class Expense(Timestamps, Base):
    __tablename__ = "expenses"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(CHAR(3), server_default="PLN")
    date: Mapped[dt.date]
    description: Mapped[str | None] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(Text)
    is_planned: Mapped[bool] = mapped_column(server_default=false())


Index("ix_expenses_user_id_date", Expense.user_id, Expense.date.desc())
