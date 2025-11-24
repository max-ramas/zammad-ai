from unittest.mock import patch

import pytest
from faststream.kafka import TestKafkaBroker
from pydantic import ValidationError

from app.core.settings import Settings
from app.kafka.broker import build_broker


@pytest.mark.asyncio
async def test_event_handler_valid_message() -> None:
    """Test event handler with a valid message."""
    with patch("app.core.settings.get_settings") as mock_settings:
        mock_settings.return_value = Settings(valid_request_types=["technischer Bürgersupport"])
        broker, event_handler = build_broker(settings=mock_settings.return_value)
        async with TestKafkaBroker(broker) as test_broker:
            message: dict = {
                "action": "created",
                "ticket": "3333",
                "status": "new",
                "statusId": "1",
                "anliegenart": "technischer Bürgersupport",
                "lhmExtId": None,
            }

            await test_broker.publish(
                topic=mock_settings.return_value.kafka.topic,
                message=message,
            )

            event_handler.mock.assert_called_once_with(message)  # type: ignore


@pytest.mark.asyncio
async def test_event_handler_with_requestType_alias() -> None:
    """Test event handler accepts requestType as alias for anliegenart."""
    with patch("app.core.settings.get_settings") as mock_settings:
        mock_settings.return_value = Settings(valid_request_types=["technischer Bürgersupport"])
        broker, event_handler = build_broker(settings=mock_settings.return_value)
        async with TestKafkaBroker(broker) as test_broker:
            message: dict = {
                "action": "created",
                "ticket": "3333",
                "status": "new",
                "statusId": "1",
                "requestType": "technischer Bürgersupport",  # Using alias
                "lhmExtId": None,
            }
            await test_broker.publish(
                topic=mock_settings.return_value.kafka.topic,
                message=message,
            )
            event_handler.mock.assert_called_once_with(message)  # type: ignore


@pytest.mark.asyncio
async def test_event_handler_invalid_request_type(caplog) -> None:
    """Test event handler skips messages with invalid request types."""
    with patch("app.core.settings.get_settings") as mock_settings:
        mock_settings.return_value = Settings(valid_request_types=["technischer Bürgersupport"])
        broker, event_handler = build_broker(settings=mock_settings.return_value)
        async with TestKafkaBroker(broker) as test_broker:
            message: dict = {
                "action": "created",
                "ticket": "3333",
                "status": "new",
                "statusId": "1",
                "anliegenart": "invalid_request_type",
                "lhmExtId": None,
            }
            with caplog.at_level("INFO"):
                await test_broker.publish(
                    topic=mock_settings.return_value.kafka.topic,
                    message=message,
                )
            assert "Skipping" in caplog.text


@pytest.mark.asyncio
async def test_event_handler_invalid_message_format() -> None:
    """Test event handler with malformed message that fails Pydantic validation."""
    with patch("app.core.settings.get_settings") as mock_settings:
        mock_settings.return_value = Settings(valid_request_types=["technischer Bürgersupport"])
        broker, event_handler = build_broker(settings=mock_settings.return_value)
        async with TestKafkaBroker(broker) as test_broker:
            # Missing required fields
            invalid_message: dict = {
                "action": "created",
                # Missing required fields: ticket, status, statusId, request_type
            }
            with pytest.raises(expected_exception=ValidationError):
                await test_broker.publish(
                    topic=mock_settings.return_value.kafka.topic,
                    message=invalid_message,
                )


@pytest.mark.asyncio
async def test_event_handler_with_multiple_valid_request_types() -> None:
    """Test event handler with multiple valid request types configured."""
    with patch("app.core.settings.get_settings") as mock_settings:
        mock_settings.return_value = Settings(valid_request_types=["technischer Bürgersupport", "general support", "other"])
        broker, event_handler = build_broker(settings=mock_settings.return_value)
        async with TestKafkaBroker(broker) as test_broker:
            message: dict = {
                "action": "created",
                "ticket": "3333",
                "status": "new",
                "statusId": "1",
                "anliegenart": "general support",
                "lhmExtId": None,
            }
            await test_broker.publish(
                topic=mock_settings.return_value.kafka.topic,
                message=message,
            )
            event_handler.mock.assert_called_once_with(message)  # type: ignore


@pytest.mark.asyncio
async def test_event_handler_case_sensitive_request_type(caplog) -> None:
    """Test that request type validation is case sensitive."""
    with patch("app.core.settings.get_settings") as mock_settings:
        mock_settings.return_value = Settings(
            valid_request_types=["technischer Bürgersupport"]  # lowercase
        )
        broker, event_handler = build_broker(settings=mock_settings.return_value)
        async with TestKafkaBroker(broker) as test_broker:
            message: dict = {
                "action": "created",
                "ticket": "3333",
                "status": "new",
                "statusId": "1",
                "anliegenart": "TECHNISCHER BÜRGERSUPPORT",  # Different case
                "lhmExtId": None,
            }
            with caplog.at_level("INFO"):
                await test_broker.publish(
                    topic=mock_settings.return_value.kafka.topic,
                    message=message,
                )
            assert "Skipping event" in caplog.text
