import logging
import sys
from typing import Optional, Any, Dict
from sqlalchemy.orm import Session


def setup_logging(log_level: str = "INFO") -> None:
    """Configure application-wide logging to stdout with a structured format."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )

    # Quieten noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def log_event(
    db: Session,
    event_type: str,
    message: str,
    level: str = "info",
    user_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist a log entry to the system_logs table.

    This function is best-effort — it will NOT raise on failure so that
    a logging error never disrupts a real request.
    """
    try:
        from ..models.log import SystemLog  # local import to avoid circular deps

        log_entry = SystemLog(
            user_id=user_id,
            event_type=event_type,
            message=message,
            level=level,
            details=details or {},
        )
        db.add(log_entry)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).error("Failed to write system log: %s", exc)
        db.rollback()
