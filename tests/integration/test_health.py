from httpx import AsyncClient


async def test_health_reports_ok_when_db_answers(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


async def test_unknown_route_uses_error_shape(client: AsyncClient) -> None:
    response = await client.get("/nope")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found", "code": "not_found"}
