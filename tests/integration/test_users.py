from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tesseract_finance.config import Settings, get_settings
from tesseract_finance.deps import get_current_user
from tesseract_finance.models import Expense, User
from tests.conftest import ClientFactory


async def test_dev_user_is_created_once_and_stored_lowercase(session: AsyncSession) -> None:
    settings = Settings(dev_user_email="Dev.Tester@Example.COM")

    first = await get_current_user(session=session, settings=settings)
    second = await get_current_user(session=session, settings=settings)

    assert first.id == second.id
    assert first.email == "dev.tester@example.com"
    count = await session.scalar(
        select(func.count()).select_from(User).where(User.email == "dev.tester@example.com")
    )
    assert count == 1


async def test_requests_without_auth_act_as_the_dev_user(
    make_client: ClientFactory, session: AsyncSession
) -> None:
    api = await make_client({get_settings: lambda: Settings(dev_user_email="solo@example.com")})

    response = await api.post("/api/v1/expenses", json={"amount": "5.00", "date": "2026-11-23"})

    assert response.status_code == 201
    owner = await session.scalar(select(User.email).join(Expense, Expense.user_id == User.id))
    assert owner == "solo@example.com"
