from unittest.mock import patch

import pytest
from faststream.exceptions import AckMessage
from faststream.kafka import TestKafkaBroker
from pydantic import ValidationError

from app.core.settings import Settings
from app.kafka.broker import broker


@pytest.mark.asyncio
async def test_event_handler_valid_message() -> None:
    """Test event handler with a valid message."""
    async with TestKafkaBroker(broker) as test_broker:
        message: dict = {
            "action": "created",
            "ticket": "3333",
            "status": "new",
            "statusId": "1",
            "anliegenart": "technischer Bürgersupport",
            "lhmExtId": None,
        }
        with patch("app.core.settings.get_settings") as mock_settings:
            mock_settings.return_value = Settings(valid_request_types=["technischer Bürgersupport"])
            with pytest.raises(AckMessage):
                await test_broker.publish(
                    topic="ticket-events",
                    message=message,
                )


@pytest.mark.asyncio
async def test_event_handler_with_requestType_alias() -> None:
    """Test event handler accepts requestType as alias for anliegenart."""
    async with TestKafkaBroker(broker) as test_broker:
        message: dict = {
            "action": "created",
            "ticket": "3333",
            "status": "new",
            "statusId": "1",
            "requestType": "technischer Bürgersupport",  # Using alias
            "lhmExtId": None,
        }
        with patch("app.core.settings.get_settings") as mock_settings:
            mock_settings.return_value = Settings(valid_request_types=["technischer Bürgersupport"])
            with pytest.raises(AckMessage):
                await test_broker.publish(
                    topic="ticket-events",
                    message=message,
                )


@pytest.mark.asyncio
async def test_event_handler_invalid_request_type() -> None:
    """Test event handler skips messages with invalid request types."""
    async with TestKafkaBroker(broker) as test_broker:
        message: dict = {
            "action": "created",
            "ticket": "3333",
            "status": "new",
            "statusId": "1",
            "anliegenart": "invalid_request_type",
            "lhmExtId": None,
        }
        with patch("app.core.settings.get_settings") as mock_settings:
            mock_settings.return_value = Settings(valid_request_types=["technischer Bürgersupport"])
            # Message should be processed and acked (with warning logged)
            with pytest.raises(AckMessage):
                await test_broker.publish(
                    topic="ticket-events",
                    message=message,
                )


@pytest.mark.asyncio
async def test_event_handler_empty_valid_request_types() -> None:
    """Test event handler with empty valid request types list."""
    async with TestKafkaBroker(broker) as test_broker:
        message: dict = {
            "action": "created",
            "ticket": "3333",
            "status": "new",
            "statusId": "1",
            "anliegenart": "any_request_type",
            "lhmExtId": None,
        }
        with patch("app.core.settings.get_settings") as mock_settings:
            mock_settings.return_value = Settings(valid_request_types=[])
            # Message should be processed and acked (with warning logged)
            with pytest.raises(AckMessage):
                await test_broker.publish(
                    topic="ticket-events",
                    message=message,
                )


@pytest.mark.asyncio
async def test_event_handler_invalid_message_format() -> None:
    """Test event handler with malformed message that fails Pydantic validation."""
    async with TestKafkaBroker(broker) as test_broker:
        # Missing required fields
        invalid_message: dict = {
            "action": "created",
            # Missing required fields: ticket, status, statusId, request_type
        }
        with patch("app.core.settings.get_settings") as mock_settings:
            mock_settings.return_value = Settings(valid_request_types=["technischer Bürgersupport"])
            # Should raise ValidationError during message processing
            with pytest.raises(ValidationError):
                await test_broker.publish(
                    topic="ticket-events",
                    message=invalid_message,
                )


@pytest.mark.asyncio
async def test_event_handler_with_multiple_valid_request_types() -> None:
    """Test event handler with multiple valid request types configured."""
    async with TestKafkaBroker(broker) as test_broker:
        message: dict = {
            "action": "created",
            "ticket": "3333",
            "status": "new",
            "statusId": "1",
            "anliegenart": "general support",
            "lhmExtId": None,
        }
        with patch("app.core.settings.get_settings") as mock_settings:
            mock_settings.return_value = Settings(valid_request_types=["technischer Bürgersupport", "general support", "other"])
            with pytest.raises(AckMessage):
                await test_broker.publish(
                    topic="ticket-events",
                    message=message,
                )


@pytest.mark.asyncio
async def test_event_handler_case_sensitive_request_type() -> None:
    """Test that request type validation is case sensitive."""
    async with TestKafkaBroker(broker) as test_broker:
        message: dict = {
            "action": "created",
            "ticket": "3333",
            "status": "new",
            "statusId": "1",
            "anliegenart": "TECHNISCHER BÜRGERSUPPORT",  # Different case
            "lhmExtId": None,
        }
        with patch("app.core.settings.get_settings") as mock_settings:
            mock_settings.return_value = Settings(
                valid_request_types=["technischer Bürgersupport"]  # lowercase
            )
            # Message should be processed and acked (with warning logged)
            with pytest.raises(AckMessage):
                await test_broker.publish(
                    topic="ticket-events",
                    message=message,
                )
