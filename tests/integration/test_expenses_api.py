import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tesseract_finance.models import Expense, User

URL = "/api/v1/expenses"
NOT_FOUND = {"detail": "Expense not found", "code": "not_found"}


async def create(api: AsyncClient, **overrides: object) -> dict:
    body = {"amount": "25.00", "date": "2026-11-23", **overrides}
    response = await api.post(URL, json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_returns_the_expense_with_defaults(api_a: AsyncClient) -> None:
    response = await api_a.post(URL, json={"amount": "25.00", "date": "2026-11-23"})

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "id": body["id"],
        "amount": "25.00",
        "currency": "PLN",
        "date": "2026-11-23",
        "description": None,
        "source_url": None,
        "is_planned": False,
        "created_at": body["created_at"],
        "updated_at": body["updated_at"],
    }
    uuid.UUID(body["id"])
    datetime.fromisoformat(body["created_at"])


async def test_create_accepts_every_field_and_normalizes_amount_and_currency(
    api_a: AsyncClient,
) -> None:
    body = await create(
        api_a,
        amount=12.5,
        currency="eur",
        description="Plectrums",
        source_url="https://example.com/order/1",
        is_planned=True,
    )

    assert body["amount"] == "12.50"
    assert body["currency"] == "EUR"
    assert body["description"] == "Plectrums"
    assert body["source_url"] == "https://example.com/order/1"
    assert body["is_planned"] is True


async def test_create_stores_amount_as_exact_decimal(
    api_a: AsyncClient, session: AsyncSession
) -> None:
    body = await create(api_a, amount=0.07)

    stored = await session.scalar(select(Expense.amount).where(Expense.id == uuid.UUID(body["id"])))
    assert stored == Decimal("0.07")


@pytest.mark.parametrize(
    "body",
    [
        {"date": "2026-11-23"},
        {"amount": "25.00"},
        {"amount": "0", "date": "2026-11-23"},
        {"amount": "-1", "date": "2026-11-23"},
        {"amount": "1.234", "date": "2026-11-23"},
        {"amount": "10000000000", "date": "2026-11-23"},
        {"amount": "abc", "date": "2026-11-23"},
        {"amount": "25.00", "date": "23.11.2026"},
        {"amount": "25.00", "date": "2026-11-23", "currency": "EURO"},
        {"amount": "25.00", "date": "2026-11-23", "currency": "E1R"},
        {"amount": "25.00", "date": "2026-11-23", "description": "x" * 501},
        {"amount": "25.00", "date": "2026-11-23", "category_id": str(uuid.uuid4())},
    ],
)
async def test_create_rejects_invalid_bodies_with_default_422(
    api_a: AsyncClient, body: dict
) -> None:
    response = await api_a.post(URL, json=body)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


async def test_get_returns_own_expense(api_a: AsyncClient) -> None:
    created = await create(api_a, description="Strings")

    response = await api_a.get(f"{URL}/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


async def test_get_missing_expense_is_404(api_a: AsyncClient) -> None:
    response = await api_a.get(f"{URL}/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


async def test_get_malformed_id_is_422(api_a: AsyncClient) -> None:
    response = await api_a.get(f"{URL}/not-a-uuid")

    assert response.status_code == 422


async def test_list_orders_by_date_then_created_at_newest_first(
    api_a: AsyncClient, session: AsyncSession, user_a: User
) -> None:
    # Inside one test transaction now() is constant, so set created_at explicitly.
    base = datetime(2026, 11, 1, tzinfo=UTC)
    rows = {
        "old": ("2026-01-01", base),
        "same-day-earlier": ("2026-06-01", base),
        "same-day-later": ("2026-06-01", base + timedelta(hours=1)),
        "newest": ("2026-12-01", base),
    }
    for description, (day, created_at) in rows.items():
        session.add(
            Expense(
                user_id=user_a.id,
                amount=Decimal("1.00"),
                date=datetime.fromisoformat(day).date(),
                description=description,
                created_at=created_at,
            )
        )
    await session.flush()

    response = await api_a.get(URL)

    assert response.status_code == 200
    body = response.json()
    assert [item["description"] for item in body["items"]] == [
        "newest",
        "same-day-later",
        "same-day-earlier",
        "old",
    ]
    assert (body["total"], body["limit"], body["offset"]) == (4, 20, 0)


async def test_list_paginates_with_limit_and_offset(api_a: AsyncClient) -> None:
    for day in ("2026-11-01", "2026-11-02", "2026-11-03"):
        await create(api_a, date=day)

    response = await api_a.get(URL, params={"limit": 1, "offset": 1})

    body = response.json()
    assert [item["date"] for item in body["items"]] == ["2026-11-02"]
    assert (body["total"], body["limit"], body["offset"]) == (3, 1, 1)


@pytest.mark.parametrize(
    "params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": "many"}]
)
async def test_list_rejects_invalid_pagination(api_a: AsyncClient, params: dict) -> None:
    response = await api_a.get(URL, params=params)

    assert response.status_code == 422


async def test_patch_changes_only_fields_in_the_body(api_a: AsyncClient) -> None:
    created = await create(
        api_a, description="Strings", source_url="https://example.com", currency="EUR"
    )

    response = await api_a.patch(f"{URL}/{created['id']}", json={"amount": 30})

    assert response.status_code == 200
    assert response.json() == {**created, "amount": "30.00"}


async def test_patch_null_clears_description_and_source_url(api_a: AsyncClient) -> None:
    created = await create(api_a, description="Strings", source_url="https://example.com")

    response = await api_a.patch(
        f"{URL}/{created['id']}", json={"description": None, "source_url": None}
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["description"], body["source_url"]) == (None, None)
    assert body["amount"] == "25.00"


async def test_patch_change_persists(api_a: AsyncClient) -> None:
    created = await create(api_a)

    await api_a.patch(
        f"{URL}/{created['id']}",
        json={"date": "2026-01-02", "currency": "usd", "is_planned": True},
    )

    body = (await api_a.get(f"{URL}/{created['id']}")).json()
    assert (body["date"], body["currency"], body["is_planned"]) == ("2026-01-02", "USD", True)


@pytest.mark.parametrize(
    "body",
    [
        {"amount": None},
        {"currency": None},
        {"date": None},
        {"is_planned": None},
        {"amount": "0.00"},
        {"amount": "1.001"},
        {"currency": "PL"},
        {"tag_ids": []},
    ],
)
async def test_patch_rejects_invalid_bodies(api_a: AsyncClient, body: dict) -> None:
    created = await create(api_a)

    response = await api_a.patch(f"{URL}/{created['id']}", json=body)

    assert response.status_code == 422


async def test_patch_missing_expense_is_404(api_a: AsyncClient) -> None:
    response = await api_a.patch(f"{URL}/{uuid.uuid4()}", json={"amount": "1.00"})

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


async def test_delete_removes_the_expense(api_a: AsyncClient) -> None:
    created = await create(api_a)

    response = await api_a.delete(f"{URL}/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert (await api_a.get(f"{URL}/{created['id']}")).status_code == 404


async def test_delete_missing_expense_is_404(api_a: AsyncClient) -> None:
    response = await api_a.delete(f"{URL}/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


async def test_other_users_expense_is_absent(api_a: AsyncClient, api_b: AsyncClient) -> None:
    created = await create(api_a, description="A's")
    url = f"{URL}/{created['id']}"

    assert (await api_b.get(url)).json() == NOT_FOUND
    patched = await api_b.patch(url, json={"description": "B was here"})
    deleted = await api_b.delete(url)
    listed = (await api_b.get(URL)).json()

    assert (patched.status_code, patched.json()) == (404, NOT_FOUND)
    assert (deleted.status_code, deleted.json()) == (404, NOT_FOUND)
    assert (listed["items"], listed["total"]) == ([], 0)
    assert (await api_a.get(url)).json() == created


async def test_database_refreshes_updated_at_on_update(
    api_a: AsyncClient, session: AsyncSession
) -> None:
    created = await create(api_a)

    stamped = await session.scalar(
        text(
            "UPDATE expenses SET updated_at = '2000-01-01T00:00:00Z' "
            "WHERE id = :id RETURNING updated_at"
        ),
        {"id": created["id"]},
    )

    assert stamped == datetime.fromisoformat(created["created_at"])


async def test_database_rejects_non_positive_amount(session: AsyncSession, user_a: User) -> None:
    with pytest.raises(IntegrityError, match="ck_expenses_amount_positive"):
        async with session.begin_nested():
            session.add(
                Expense(user_id=user_a.id, amount=Decimal("0"), date=datetime(2026, 1, 1).date())
            )
