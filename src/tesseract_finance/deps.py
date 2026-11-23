from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from tesseract_finance.config import Settings, get_settings
from tesseract_finance.db import get_session
from tesseract_finance.models import User
from tesseract_finance.schemas.pagination import PageParams
from tesseract_finance.services.users import ensure_user

SessionDep = Annotated[AsyncSession, Depends(get_session)]
Pagination = Annotated[PageParams, Query()]


async def get_current_user(
    session: SessionDep, settings: Annotated[Settings, Depends(get_settings)]
) -> User:
    """Pre-M4 stand-in: every request acts as the DEV_USER_EMAIL user. M4 swaps in JWT."""
    return await ensure_user(session, settings.dev_user_email)


CurrentUser = Annotated[User, Depends(get_current_user)]
