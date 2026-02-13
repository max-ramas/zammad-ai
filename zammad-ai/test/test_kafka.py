from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.exceptions import RequestValidationError
from faststream.kafka import TestKafkaBroker

from app.kafka.broker import build_router
from app.models.triage import TriageResult
from app.settings import ZammadAISettings
from app.settings.triage import Action, Category


@pytest.fixture
def mock_triage() -> MagicMock:
    """
    Create a MagicMock that simulates a Triage with a preset async `perform_triage` result.

    Returns:
        MagicMock: A mock Triage object whose `perform_triage` is an AsyncMock returning a
        TriageResult with a Category(name="Test", id=1), Action(name="Test", description="Test", id=1),
        reasoning "Test reasoning", and confidence 0.95.
    """
    triage = MagicMock()
    # Make perform_triage return an async mock that returns a TriageResult
    triage.perform_triage = AsyncMock(
        return_value=TriageResult(
            category=Category(name="Test", id=1),
            action=Action(name="Test", description="Test", id=1),
            reasoning="Test reasoning",
            confidence=0.95,
        )
    )
    return triage


@pytest.fixture
def mock_get_triage(monkeypatch: pytest.MonkeyPatch, mock_triage: MagicMock) -> None:
    """Patch Kafka router triage lookup to return a mocked triage object."""
    monkeypatch.setattr("app.kafka.broker.get_triage", lambda *args, **kwargs: mock_triage)


@pytest.mark.asyncio
async def test_event_handler_valid_message(
    kafka_message_factory: Callable[..., dict[str, str]],
    mock_triage: MagicMock,
    mock_get_triage: None,
    settings_factory: Callable[..., ZammadAISettings],
) -> None:
    """Test event handler with a valid message."""
    settings = settings_factory(valid_request_types=["technischer Bürgersupport"])
    router, event_handler = build_router(settings=settings)
    async with TestKafkaBroker(router.broker) as test_broker:
        message = kafka_message_factory()
        await test_broker.publish(topic=settings.kafka.topic, message=message)
        # Verify the triage was called with the correct ticket ID
        mock_triage.perform_triage.assert_called_once_with(id="3720")


@pytest.mark.asyncio
async def test_event_handler_with_requestType_alias(
    kafka_message_factory: Callable[..., dict[str, str]],
    mock_triage: MagicMock,
    mock_get_triage: None,
    settings_factory: Callable[..., ZammadAISettings],
) -> None:
    """Test event handler accepts requestType as alias for anliegenart."""
    settings = settings_factory(valid_request_types=["technischer Bürgersupport"])
    router, event_handler = build_router(settings=settings)
    async with TestKafkaBroker(router.broker) as test_broker:
        message = kafka_message_factory()
        # Use alias instead of anliegenart
        message.pop("anliegenart", None)
        message["requestType"] = "technischer Bürgersupport"
        await test_broker.publish(topic=settings.kafka.topic, message=message)
        # Verify the triage was called with the correct ticket ID
        mock_triage.perform_triage.assert_called_once_with(id="3720")


@pytest.mark.asyncio
async def test_event_handler_invalid_request_type(
    kafka_message_factory: Callable[..., dict[str, str]],
    mock_triage: MagicMock,
    mock_get_triage: None,
    settings_factory: Callable[..., ZammadAISettings],
    caplog,
) -> None:
    """Test event handler skips messages with invalid request types."""
    settings = settings_factory(valid_request_types=["technischer Bürgersupport"])
    router, event_handler = build_router(settings=settings)
    async with TestKafkaBroker(router.broker) as test_broker:
        message = kafka_message_factory(anliegenart="invalid_request_type")
        message["anliegenart"] = "invalid_request_type"
        with caplog.at_level("INFO"):
            await test_broker.publish(topic=settings.kafka.topic, message=message)
        assert "Skipping" in caplog.text
        # Verify triage was NOT called for invalid request types
        mock_triage.perform_triage.assert_not_called()


@pytest.mark.asyncio
async def test_event_handler_invalid_message_format(
    mock_triage: MagicMock,
    mock_get_triage: None,
    settings_factory: Callable[..., ZammadAISettings],
) -> None:
    """Test event handler with malformed message that fails Pydantic validation."""
    settings = settings_factory(valid_request_types=["technischer Bürgersupport"])
    router, event_handler = build_router(settings=settings)
    async with TestKafkaBroker(router.broker) as test_broker:
        # Missing required fields
        invalid_message: dict = {
            "action": "created",
            # Missing required fields: ticket, status, statusId, request_type
        }
        with pytest.raises(expected_exception=RequestValidationError):
            await test_broker.publish(topic=settings.kafka.topic, message=invalid_message)


@pytest.mark.asyncio
async def test_event_handler_with_multiple_valid_request_types(
    kafka_message_factory: Callable[..., dict[str, str]],
    mock_triage: MagicMock,
    mock_get_triage: None,
    settings_factory: Callable[..., ZammadAISettings],
) -> None:
    """Test event handler with multiple valid request types configured."""
    settings = settings_factory(valid_request_types=["technischer Bürgersupport", "general support", "other"])
    router, event_handler = build_router(settings=settings)
    async with TestKafkaBroker(router.broker) as test_broker:
        message = kafka_message_factory(anliegenart="general support")
        await test_broker.publish(topic=settings.kafka.topic, message=message)
        # Verify the triage was called with the correct ticket ID
        mock_triage.perform_triage.assert_called_once_with(id="3720")


@pytest.mark.asyncio
async def test_event_handler_case_sensitive_request_type(
    kafka_message_factory: Callable[..., dict[str, str]],
    mock_triage: MagicMock,
    mock_get_triage: None,
    settings_factory: Callable[..., ZammadAISettings],
    caplog,
) -> None:
    """Test that request type validation is case sensitive."""
    settings = settings_factory(valid_request_types=["technischer Bürgersupport"])
    router, event_handler = build_router(settings=settings)
    async with TestKafkaBroker(router.broker) as test_broker:
        message = kafka_message_factory(anliegenart="TECHNISCHER BÜRGERSUPPORT")
        with caplog.at_level("INFO"):
            await test_broker.publish(topic=settings.kafka.topic, message=message)
        assert "Skipping event" in caplog.text
        # Verify triage was NOT called for case mismatch
        mock_triage.perform_triage.assert_not_called()
