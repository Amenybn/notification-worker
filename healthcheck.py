"""Sonde de vie sans HTTP : code 0 si le worker a écrit son heartbeat récemment."""
import os
import sys
from datetime import datetime, timezone

poll = max(1, int(os.getenv("POLL_SECONDS", "5")))
max_age = max(poll * 3, 30)
try:
    with open(os.getenv("HEARTBEAT_FILE", "/tmp/notification-worker-heartbeat"), encoding="utf-8") as f:
        last = datetime.fromisoformat(f.read().strip())
    sys.exit(0 if (datetime.now(timezone.utc) - last).total_seconds() <= max_age else 1)
except Exception:
    sys.exit(1)
