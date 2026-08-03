from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings


def register_cors(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )