import time
import uuid

from app.core.logger import app_logger


def register_request_logger(app) -> None:
    @app.middleware("http")
    async def log_request(request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        started_at = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started_at) * 1000
            app_logger.exception(
                "Request failed: {} {} request_id={} duration_ms={:.2f}",
                request.method,
                request.url.path,
                request_id,
                duration_ms,
            )
            raise

        duration_ms = (time.perf_counter() - started_at) * 1000
        response.headers["X-Request-ID"] = request_id
        app_logger.info(
            "Request completed: {} {} status={} request_id={} duration_ms={:.2f}",
            request.method,
            request.url.path,
            response.status_code,
            request_id,
            duration_ms,
        )
        return response
