import traceback

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logger import app_logger


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        app_logger.warning("Validation error: {} {} - {}", request.method, request.url.path, exc.errors())
        return JSONResponse(status_code=422, content={"detail": "Request validation failed"})

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        app_logger.warning("HTTP error: {} {} - {}", request.method, request.url.path, exc.status_code)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        app_logger.exception(
            "Unhandled exception on {} {}: {}",
            request.method,
            request.url.path,
            repr(exc),
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred. Please try again later."},
        )
