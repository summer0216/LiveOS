"""Development-only trace for one public rent evidence search execution."""

import json
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import settings


TRACE_PATH = Path(tempfile.gettempdir()) / "liveos-external-rent-search-observability.jsonl"


def record_external_rent_search_trace(execution_id: str, event: str, **fields: Any) -> None:
    """Append bounded stage metadata without allowing tracing to affect the action."""
    if settings.APP_ENV != "development":
        return
    try:
        with TRACE_PATH.open("a", encoding="utf-8") as trace:
            trace.write(json.dumps({
                "execution_id": execution_id,
                "event": event,
                **fields,
            }, ensure_ascii=False) + "\n")
    except OSError:
        return
