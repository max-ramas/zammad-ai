from logging import Logger
from typing import Annotated

from faststream import AckPolicy, Depends, FastStream
from faststream.exceptions import AckMessage, NackMessage
from faststream.kafka import KafkaBroker
from faststream.kafka.annotations import KafkaMessage

from app.core.settings import Settings, get_settings
from app.models.kafka import Event
from app.utils.logging import getLogger

from .security import setup_security

logger: Logger = getLogger("zammad-ai.app.kafka")
settings: Settings = get_settings()

# Security setup
security = setup_security()

# Kafka Broker and FastStream app setup
broker = KafkaBroker(
    bootstrap_servers=settings.kafka.broker_url,
    security=security,
)
app = FastStream(broker)


@broker.subscriber(
    settings.kafka.topic,
    # group_id=settings.kafka.group_id,
    ack_policy=AckPolicy.ACK_FIRST,  # To ensure exactly-once processing
)
async def event_handler(
    event: Event,
    msg: KafkaMessage,
    injected_settings: Annotated[Settings, Depends(get_settings)],
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
    if event.request_type not in injected_settings.valid_request_types:
        logger.warning(f"Skipping event with request type: {event.request_type}")
        raise AckMessage()

    if False:  # Replace with error handlers
        raise NackMessage()

    await msg.ack()
