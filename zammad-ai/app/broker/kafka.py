from logging import Logger
from typing import Annotated

from faststream import AckPolicy, Depends, FastStream
from faststream.exceptions import AckMessage, NackMessage
from faststream.kafka import KafkaBroker
from faststream.kafka.annotations import KafkaMessage

from app.core.settings import Settings, get_settings
from app.models.kafka import Event
from app.utils.logging import getLogger

logger: Logger = getLogger("zammad-ai.app.kafka")
settings: Settings = get_settings()

broker = KafkaBroker(bootstrap_servers=settings.kafka.broker_url)
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
    logger.debug(f"Received event: {event}")

    # Filter here because information from body is needed
    if event.request_type not in injected_settings.valid_request_types:
        logger.warning(f"Skipping event with request type: {event.request_type}")
        raise AckMessage()

    if False:  # Replace with error handlers
        raise NackMessage()

    await msg.ack()
