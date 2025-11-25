import pytest
from faststream.kafka import TestKafkaBroker
from pydantic import ValidationError

from app.core.settings import Settings
from app.kafka.broker import build_broker


@pytest.fixture
def valid_message() -> dict:
    """Standard valid test message."""
    return {
        "action": "created",
        "ticket": "3333",
        "status": "new",
        "statusId": "1",
        "anliegenart": "technischer Bürgersupport",
        "lhmExtId": None,
    }


@pytest.mark.asyncio
async def test_event_handler_valid_message(valid_message: dict) -> None:
    """Test event handler with a valid message."""
    settings = Settings(valid_request_types=["technischer Bürgersupport"])
    broker, event_handler = build_broker(settings=settings)
    async with TestKafkaBroker(broker) as test_broker:
        # copy fixture to avoid mutating the shared dict if a test modifies it
        message = dict(valid_message)
        await test_broker.publish(topic=settings.kafka.topic, message=message)
        event_handler.mock.assert_called_once_with(message)  # type: ignore


@pytest.mark.asyncio
async def test_event_handler_with_requestType_alias(valid_message: dict) -> None:
    """Test event handler accepts requestType as alias for anliegenart."""
    settings = Settings(valid_request_types=["technischer Bürgersupport"])
    broker, event_handler = build_broker(settings=settings)
    async with TestKafkaBroker(broker) as test_broker:
        message = dict(valid_message)
        # Use alias instead of anliegenart
        message.pop("anliegenart", None)
        message["requestType"] = "technischer Bürgersupport"
        await test_broker.publish(topic=settings.kafka.topic, message=message)
        event_handler.mock.assert_called_once_with(message)  # type: ignore


@pytest.mark.asyncio
async def test_event_handler_invalid_request_type(valid_message: dict, caplog) -> None:
    """Test event handler skips messages with invalid request types."""
    settings = Settings(valid_request_types=["technischer Bürgersupport"])
    broker, event_handler = build_broker(settings=settings)
    async with TestKafkaBroker(broker) as test_broker:
        message = dict(valid_message)
        message["anliegenart"] = "invalid_request_type"
        with caplog.at_level("INFO"):
            await test_broker.publish(topic=settings.kafka.topic, message=message)
        assert "Skipping" in caplog.text


@pytest.mark.asyncio
async def test_event_handler_invalid_message_format() -> None:
    """Test event handler with malformed message that fails Pydantic validation."""
    settings = Settings(valid_request_types=["technischer Bürgersupport"])
    broker, event_handler = build_broker(settings=settings)
    async with TestKafkaBroker(broker) as test_broker:
        # Missing required fields
        invalid_message: dict = {
            "action": "created",
            # Missing required fields: ticket, status, statusId, request_type
        }
        with pytest.raises(expected_exception=ValidationError):
            await test_broker.publish(topic=settings.kafka.topic, message=invalid_message)


@pytest.mark.asyncio
async def test_event_handler_with_multiple_valid_request_types(valid_message: dict) -> None:
    """Test event handler with multiple valid request types configured."""
    settings = Settings(valid_request_types=["technischer Bürgersupport", "general support", "other"])
    broker, event_handler = build_broker(settings=settings)
    async with TestKafkaBroker(broker) as test_broker:
        message = dict(valid_message)
        message["anliegenart"] = "general support"
        await test_broker.publish(topic=settings.kafka.topic, message=message)
        event_handler.mock.assert_called_once_with(message)  # type: ignore


@pytest.mark.asyncio
async def test_event_handler_case_sensitive_request_type(valid_message: dict, caplog) -> None:
    """Test that request type validation is case sensitive."""
    settings = Settings(
        valid_request_types=["technischer Bürgersupport"]  # exact case
    )
    broker, event_handler = build_broker(settings=settings)
    async with TestKafkaBroker(broker) as test_broker:
        message = dict(valid_message)
        message["anliegenart"] = "TECHNISCHER BÜRGERSUPPORT"  # Different case
        with caplog.at_level("INFO"):
            await test_broker.publish(topic=settings.kafka.topic, message=message)
        assert "Skipping event" in caplog.text
