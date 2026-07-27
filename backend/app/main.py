from fastapi import FastAPI

from app.api.router import api_router
from app.core.exceptions import register_exception_handlers
from app.core.lifespan import lifespan
from app.middleware.cors import register_cors
from app.middleware.request_logger import register_request_logger

app = FastAPI(
    title="Job Auto Apply",
    version="1.0.0",
    lifespan=lifespan,
)

register_cors(app)
register_request_logger(app)
register_exception_handlers(app)

app.include_router(
    api_router,
    prefix="/api",
)


@app.get("/")
def root():
    return {
        "message": "Job Auto Apply Backend"
    }