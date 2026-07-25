from pathlib import Path

from loguru import logger

LOG_DIR = Path("logs")

LOG_DIR.mkdir(exist_ok=True)

logger.add(
    LOG_DIR / "backend.log",
    rotation="10 MB",
    retention="10 days",
    level="INFO",
)

app_logger = logger