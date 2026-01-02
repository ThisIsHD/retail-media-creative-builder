import json
import logging
from datetime import datetime, timezone

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    h = logging.StreamHandler()
    h.setFormatter(JsonFormatter())
    root.addHandler(h)
