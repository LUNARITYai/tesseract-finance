import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tesseract_finance.models import Expense
from tesseract_finance.schemas.expenses import ExpenseCreate, ExpenseUpdate
from tesseract_finance.schemas.pagination import PageParams


class ExpenseService:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id

    async def create(self, data: ExpenseCreate) -> Expense:
        expense = Expense(user_id=self.user_id, **data.model_dump())
        self.session.add(expense)
        await self.session.commit()
        return expense

    async def list(self, page: PageParams) -> tuple[Sequence[Expense], int]:
        owned = Expense.user_id == self.user_id
        total = await self.session.scalar(select(func.count()).select_from(Expense).where(owned))
        items = await self.session.scalars(
            select(Expense)
            .where(owned)
            .order_by(Expense.date.desc(), Expense.created_at.desc(), Expense.id.desc())
            .limit(page.limit)
            .offset(page.offset)
        )
        return items.all(), total or 0

    async def get(self, expense_id: uuid.UUID) -> Expense | None:
        return await self.session.scalar(
            select(Expense).where(Expense.id == expense_id, Expense.user_id == self.user_id)
        )

    async def update(self, expense_id: uuid.UUID, changes: ExpenseUpdate) -> Expense | None:
        expense = await self.get(expense_id)
        if expense is None:
            return None
        for name, value in changes.model_dump(exclude_unset=True).items():
            setattr(expense, name, value)
        await self.session.commit()
        return expense

    async def delete(self, expense_id: uuid.UUID) -> bool:
        expense = await self.get(expense_id)
        if expense is None:
            return False
        await self.session.delete(expense)
        await self.session.commit()
        return True
