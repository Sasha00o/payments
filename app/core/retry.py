from __future__ import annotations

import random

from app.core.config import settings


def compute_retry_delay(attempt_count: int) -> float:
    """Экспоненциальная задержка с потолком и jitter."""
    base_delay = min(
        settings.RETRY_BASE_DELAY ** max(attempt_count, 1),
        settings.RETRY_MAX_DELAY,
    )
    jitter = random.uniform(0, settings.RETRY_JITTER_MAX)
    return base_delay + jitter
