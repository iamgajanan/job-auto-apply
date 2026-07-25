import time

from app.core.logger import app_logger


def register_request_logger(app):

    @app.middleware("http")
    async def log_request(request, call_next):

        start = time.time()

        response = await call_next(request)

        duration = time.time() - start

        app_logger.info(
            f"{request.method} "
            f"{request.url.path} "
            f"{duration:.3f}s"
        )

        return response