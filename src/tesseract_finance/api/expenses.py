import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from tesseract_finance.deps import CurrentUser, Pagination, SessionDep
from tesseract_finance.models import Expense
from tesseract_finance.schemas.expenses import ExpenseCreate, ExpenseRead, ExpenseUpdate
from tesseract_finance.schemas.pagination import Page
from tesseract_finance.services.expenses import ExpenseService

router = APIRouter(prefix="/api/v1/expenses", tags=["expenses"])


def get_expense_service(session: SessionDep, user: CurrentUser) -> ExpenseService:
    return ExpenseService(session, user.id)


Service = Annotated[ExpenseService, Depends(get_expense_service)]


def found(expense: Expense | None) -> Expense:
    if expense is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")
    return expense


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_expense(body: ExpenseCreate, service: Service) -> ExpenseRead:
    return ExpenseRead.model_validate(await service.create(body))


@router.get("")
async def list_expenses(page: Pagination, service: Service) -> Page[ExpenseRead]:
    items, total = await service.list(page)
    return Page[ExpenseRead](
        items=[ExpenseRead.model_validate(item) for item in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{expense_id}")
async def get_expense(expense_id: uuid.UUID, service: Service) -> ExpenseRead:
    return ExpenseRead.model_validate(found(await service.get(expense_id)))


@router.patch("/{expense_id}")
async def update_expense(
    expense_id: uuid.UUID, body: ExpenseUpdate, service: Service
) -> ExpenseRead:
    return ExpenseRead.model_validate(found(await service.update(expense_id, body)))


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(expense_id: uuid.UUID, service: Service) -> Response:
    if not await service.delete(expense_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
