from fastapi import APIRouter

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"],
)


@router.get("/health")
def health():
    return {
        "message": "Jobs API Working"
    }