import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from tesseract_finance.models.base import Base, Timestamps


class User(Timestamps, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String)
