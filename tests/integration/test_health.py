from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession


async def test_health_reports_ok_when_db_answers(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


async def test_unknown_route_uses_error_shape(client: AsyncClient) -> None:
    response = await client.get("/nope")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found", "code": "not_found"}


async def test_session_commit_does_not_escape(
    session: AsyncSession,
    committed_connection: AsyncConnection,
) -> None:
    await session.execute(text("CREATE TABLE rollback_probe (id integer)"))
    await session.commit()
    await session.execute(text("INSERT INTO rollback_probe (id) VALUES (1)"))
    await session.commit()
    count = await session.scalar(text("SELECT count(*) FROM rollback_probe"))
    assert count == 1

    visible = await committed_connection.scalar(text("SELECT to_regclass('public.rollback_probe')"))
    assert visible is None
