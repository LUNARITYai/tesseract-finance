from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from tesseract_finance.api import health


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Give every HTTP error the spec's {"detail", "code"} shape.

    The code is derived from the status (404 -> "not_found"), so routers raise a
    plain HTTPException and never pick codes by hand.
    """
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
    return app


app = create_app()
