import sys
from pathlib import Path

from loguru import logger

LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    enqueue=True,
    backtrace=False,
    diagnose=False,
)
logger.add(
    LOG_DIR / "backend.log",
    rotation="10 MB",
    retention="10 days",
    level="INFO",
    enqueue=True,
    backtrace=False,
    diagnose=False,
)

app_logger = logger
