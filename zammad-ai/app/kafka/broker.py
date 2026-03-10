from collections.abc import Callable
from logging import Logger

from faststream import AckPolicy
from faststream.exceptions import AckMessage, NackMessage
from faststream.kafka.fastapi import KafkaRouter
from faststream.security import BaseSecurity

from app.core.settings import ZammadAISettings
from app.models.kafka import Event
from app.models.triage import TriageResult
from app.triage.triage import get_triage
from app.utils.logging import getLogger

from ..triage.triage import Triage
from .security import setup_security

logger: Logger = getLogger(name="zammad-ai")


def build_router(settings: ZammadAISettings) -> tuple[KafkaRouter, Callable]:
    """
    Create a configured KafkaRouter and its subscriber event handler for ticket triage.

    Parameters:
        settings (ZammadAISettings): Application settings containing Kafka configuration and valid request types.

    Returns:
        tuple[KafkaRouter, Callable]: The configured KafkaRouter and its event handler callable.
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
        """
        Process an incoming Kafka event to perform ticket triage and acknowledge the message.

        If the event's request type is not supported, the event is acknowledged and skipped. The handler attempts to perform triage for the event's ticket, logs any processing errors, and acknowledges the event when finished.

        Args:
            event (Event): The Kafka event to process.

        Raises:
            AckMessage: Acknowledges the Kafka message to mark it as processed.
        """
        logger.debug(f"Received event: {event}")

        # Filter here because information from body is needed
        if event.request_type not in settings.valid_request_types:
            logger.info(f"Skipping event with request type: {event.request_type}")
            raise AckMessage()

        if False:  # TODO: Replace with error handlers
            raise NackMessage()
        try:
            triage: Triage = get_triage(settings=settings)
            id: int = int(event.ticket)
            result: TriageResult = await triage.perform_triage(id=id)
            logger.debug(f"Triage result for ticket {id}: {result}")
        except Exception:
            logger.error(f"Error processing event for ticket {event.ticket}.", exc_info=True)
            raise NackMessage()
        raise AckMessage()

    return router, event_handler
