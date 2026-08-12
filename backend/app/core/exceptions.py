import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.logger import app_logger


def register_exception_handlers(app: FastAPI):

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request,
        exc: Exception,
    ):
        # Log the full traceback internally — never send it to the client.
        app_logger.error(
            "Unhandled exception on {} {}: {}\n{}",
            request.method,
            request.url.path,
            repr(exc),
            traceback.format_exc(),
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An unexpected error occurred. Please try again later.",
            },
        )