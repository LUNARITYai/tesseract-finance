"""Migration roundtrip on its own database, so downgrading never touches the test schema."""

import asyncio
import os
import sys

from sqlalchemy.engine import make_url

from tesseract_finance.config import get_settings
from tests.conftest import ROOT, ensure_database


def migrate_database_url() -> str:
    """The test database URL with ``_test`` swapped for ``_migrate`` in the name."""
    url = make_url(get_settings().database_url)
    assert url.database and "_test" in url.database
    return url.set(database=url.database.replace("_test", "_migrate", 1)).render_as_string(
        hide_password=False
    )


async def alembic(*args: str, database_url: str) -> None:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "alembic",
        *args,
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": database_url},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await process.communicate()
    assert process.returncode == 0, f"alembic {' '.join(args)} failed:\n{output.decode()}"


async def test_migrations_roundtrip_and_match_models() -> None:
    url = migrate_database_url()
    await ensure_database(url)

    await alembic("upgrade", "head", database_url=url)
    await alembic("downgrade", "base", database_url=url)
    await alembic("upgrade", "head", database_url=url)
    await alembic("check", database_url=url)
