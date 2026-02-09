from logging import Logger
from typing import Callable

from faststream import AckPolicy
from faststream.exceptions import AckMessage, NackMessage
from faststream.kafka.fastapi import KafkaRouter
from faststream.security import BaseSecurity

from app.core.context import get_backend_context
from app.core.settings import ZammadAISettings
from app.models.kafka import Event
from app.models.triage import TriageResult
from app.utils.logging import getLogger

from .security import setup_security

logger: Logger = getLogger("zammad-ai")


def build_router(settings: ZammadAISettings) -> tuple[KafkaRouter, Callable]:
    """Build and return a KafkaRouter instance and its event handler.

    Args:
        settings (ZammadAISettings): The application settings.

    Returns:
        tuple[KafkaRouter, Callable]: The configured KafkaRouter and its event handler.
    """
    logger.info("Building Kafka router")

    # Security setup
    security: BaseSecurity = setup_security(kafka_settings=settings.kafka)

    # Kafka Router
    router = KafkaRouter(
        bootstrap_servers=settings.kafka.broker_url,
        security=security,
    )

    @router.subscriber(
        settings.kafka.topic,
        group_id=settings.kafka.group_id,
        ack_policy=AckPolicy.NACK_ON_ERROR,
    )
    async def event_handler(
        event: Event,
    ) -> None:
        """Handle incoming Kafka events for ticket processing.

        Args:
            event (Event): The Kafka event to process.

        Raises:
            AckMessage: If the event is processed successfully.
            NackMessage: If the event processing fails.
        """
        logger.debug(f"Received event: {event}")

        # Filter here because information from body is needed
        if event.request_type not in settings.valid_request_types:
            logger.info(f"Skipping event with request type: {event.request_type}")
            raise AckMessage()

        if False:  # Replace with error handlers
            raise NackMessage()
        try:
            triage = get_backend_context().triage
            id = event.ticket
            result: TriageResult = await triage.perform_triage(id=id)
            logger.debug(f"Triage result for ticket {id}: {result}")
        except Exception as e:
            logger.error(f"Error processing event for ticket {event.ticket}: {e}")
        raise AckMessage()

    return router, event_handler
