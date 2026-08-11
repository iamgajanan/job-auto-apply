from fastapi import APIRouter, HTTPException

from app.db.connection import check_database_connection

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get("/database")
def database_health():
    try:
        check_database_connection()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        ) from exc

    return {"status": "ok", "database": "connected"}
