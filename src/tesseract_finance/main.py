from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from tesseract_finance.api import expenses, health


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = HTTPStatus(exc.status_code).phrase.lower().replace(" ", "_").replace("-", "_")
    return JSONResponse(
        {"detail": exc.detail, "code": code},
        status_code=exc.status_code,
        headers=exc.headers,
    )


def create_app() -> FastAPI:
    app = FastAPI(title="TesseractFinance")
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.include_router(health.router)
    app.include_router(expenses.router)
    return app


app = create_app()
