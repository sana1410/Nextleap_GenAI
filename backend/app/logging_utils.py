"""One JSON object per log line. Fields are passed explicitly so secrets and prompts are never logged."""
import json
import logging
from typing import Any

events = logging.getLogger("app.events")


def log_event(event: str, **fields: Any) -> None:
    events.info(json.dumps({"event": event, **fields}, default=str, ensure_ascii=False))


def configure_logging() -> None:
    """Make app.* INFO logs visible under uvicorn (which only configures its own loggers)."""
    if logging.getLogger().handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    app_logger = logging.getLogger("app")
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)
