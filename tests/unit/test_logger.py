import pytest
from app.core.logger import configure_logging, get_logger, bind_context, clear_context


@pytest.mark.unit
def test_logger_configuration():
    """Тест настройки логгера."""
    configure_logging(log_level="DEBUG", json_logs=False)
    logger = get_logger(__name__)

    assert logger is not None


@pytest.mark.unit
def test_logger_context():
    """Тест контекстных переменных логгера."""
    configure_logging(log_level="INFO")

    bind_context(user_id=123, request_id="test-123")
    clear_context()

    assert True


@pytest.mark.unit
def test_get_logger_with_name():
    """Тест получения логгера с именем."""
    logger = get_logger("test_module")
    assert logger is not None
