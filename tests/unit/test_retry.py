from unittest.mock import patch

import pytest

from app.core.config import settings
from app.core.retry import compute_retry_delay


@pytest.mark.unit
def test_base_delay_grows_until_capped():
    """Базовая задержка растёт экспоненциально и упирается в RETRY_MAX_DELAY."""
    with patch('app.core.retry.random.uniform', return_value=0):
        delay_attempt_1 = compute_retry_delay(1)
        delay_attempt_2 = compute_retry_delay(2)
        delay_attempt_10 = compute_retry_delay(10)

    assert delay_attempt_1 == settings.RETRY_BASE_DELAY
    assert delay_attempt_2 == settings.RETRY_BASE_DELAY ** 2
    assert delay_attempt_10 == settings.RETRY_MAX_DELAY
    assert delay_attempt_1 < delay_attempt_2 <= delay_attempt_10


@pytest.mark.unit
def test_delay_includes_jitter():
    """Jitter добавляется поверх базовой задержки."""
    with patch('app.core.retry.random.uniform', return_value=0.25):
        delay = compute_retry_delay(1)

    assert delay == settings.RETRY_BASE_DELAY + 0.25


@pytest.mark.unit
def test_delay_respects_upper_bound():
    """Итоговая задержка не превышает потолок + максимальный jitter."""
    with patch('app.core.retry.random.uniform', return_value=settings.RETRY_JITTER_MAX):
        delay = compute_retry_delay(100)

    assert delay == settings.RETRY_MAX_DELAY + settings.RETRY_JITTER_MAX
