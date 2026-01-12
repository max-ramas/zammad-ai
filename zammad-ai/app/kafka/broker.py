from logging import Logger
from typing import Callable

from faststream import AckPolicy
from faststream.exceptions import AckMessage, NackMessage
from faststream.kafka import KafkaBroker
from faststream.kafka.annotations import KafkaMessage
from faststream.security import BaseSecurity

from app.core.settings import Settings
from app.models.kafka import Event
from app.models.triage import TriageResult
from app.triage.triage import Triage
from app.utils.logging import getLogger

from .security import setup_security

logger: Logger = getLogger("zammad-ai")


def build_broker(settings: Settings) -> tuple[KafkaBroker, Callable]:
    """Build and return a KafkaBroker instance and its event handler.

    Args:
        settings (Settings): The application settings.

    Returns:
        tuple[KafkaBroker, Callable]: The configured KafkaBroker and its event handler.
    """
    logger.info("Building Kafka broker")

    # Security setup
    security: BaseSecurity = setup_security(settings=settings)

    # Kafka Broker and FastStream app setup
    broker = KafkaBroker(
        bootstrap_servers=settings.kafka.broker_url,
        security=security,
    )

    @broker.subscriber(
        settings.kafka.topic,
        group_id=settings.kafka.group_id,
        ack_policy=AckPolicy.NACK_ON_ERROR,
    )
    async def event_handler(
        event: Event,
        msg: KafkaMessage,
    ) -> None:
        """Handle incoming Kafka events for ticket processing.

        Args:
            event (Event): The Kafka event to process.
            msg (KafkaMessage): The Kafka message metadata.
            injected_settings (Annotated[Settings, Depends]): The application settings, injected via dependency injection.

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

        await msg.ack()
        triage = Triage()
        id = event.ticket
        result: TriageResult = await triage.perform_triage(id=id)
        logger.info(f"Triage result for ticket {id}: {result}")
        raise AckMessage()

    return broker, event_handler
