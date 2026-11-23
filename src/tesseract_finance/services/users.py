from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from tesseract_finance.models import User


async def ensure_user(session: AsyncSession, email: str) -> User:
    email = email.strip().lower()
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        await session.execute(
            insert(User).values(email=email).on_conflict_do_nothing(index_elements=[User.email])
        )
        await session.commit()
        user = await session.scalar(select(User).where(User.email == email))
    assert user is not None
    return user
