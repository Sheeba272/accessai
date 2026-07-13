"""Centralized logging configuration"""
import logging
import sys
from backend.utils.config import settings


def setup_logger():
    level = logging.DEBUG if settings.DEBUG else logging.INFO
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("data/accessai.log", encoding="utf-8"),
        ],
    )

    # Quiet noisy libs
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # ADD THESE
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)