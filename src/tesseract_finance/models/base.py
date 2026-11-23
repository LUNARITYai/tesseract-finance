from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime, FetchedValue, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Fetch server-set columns (created_at, trigger-set updated_at) via RETURNING
    # on INSERT and UPDATE, so ORM objects never hold stale timestamps.
    __mapper_args__: ClassVar[dict[str, Any]] = {"eager_defaults": True}


UPDATED_AT_FUNCTION = "set_updated_at"

CREATE_UPDATED_AT_FUNCTION = f"""
CREATE FUNCTION {UPDATED_AT_FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$
"""


def create_updated_at_trigger(table: str) -> str:
    return (
        f"CREATE TRIGGER {table}_{UPDATED_AT_FUNCTION} BEFORE UPDATE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {UPDATED_AT_FUNCTION}()"
    )


def drop_updated_at_trigger(table: str) -> str:
    return f"DROP TRIGGER {table}_{UPDATED_AT_FUNCTION} ON {table}"


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        server_onupdate=FetchedValue(),
    )
