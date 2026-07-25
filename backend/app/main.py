from fastapi import FastAPI
from sqlalchemy import text

from app.config.settings import settings
from app.database.database import engine
from app.database.redis import redis_client

app = FastAPI(title=settings.APP_NAME)


@app.get("/")
def home():
    return {
        "message": "Backend Running"
    }


@app.get("/health")
def health():

    database = False

    redis = False

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            database = True
    except Exception:
        pass

    try:
        redis_client.ping()
        redis = True
    except Exception:
        pass

    return {
        "database": database,
        "redis": redis
    }