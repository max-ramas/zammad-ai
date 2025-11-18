from logging import Logger
from typing import Annotated

from faststream import AckPolicy, Depends, FastStream
from faststream.exceptions import AckMessage, NackMessage
from faststream.kafka import KafkaBroker
from faststream.kafka.annotations import KafkaMessage
from pydantic import AliasChoices, BaseModel, Field

from .logtools import getLogger
from .settings import Settings, get_settings

logger: Logger = getLogger("zammad-ai.app.kafka")
settings: Settings = get_settings()

broker = KafkaBroker(bootstrap_servers=settings.kafka.broker_url)
app = FastStream(broker)


class Event(BaseModel):
    """Event model for Kafka messages.

    Follows this structure: https://github.com/it-at-m/dbs/blob/main/ticketing-eventing/handler-core/src/main/java/de/muenchen/oss/dbs/ticketing/eventing/handlercore/domain/model/Event.java
    """

    action: str = Field(
        description="Action performed on the ticket",
        examples=["created"],
    )
    ticket: str = Field(
        description="ID of the ticket",
        examples=["3720"],
    )
    status: str = Field(
        description="Current status of the ticket",
        examples=["new"],
    )
    statusId: str = Field(
        description="ID of the current status",
        examples=["1"],
    )
    request_type: str = Field(
        validation_alias=AliasChoices("anliegenart", "requestType"),
        description="Type of request",
        examples=["technischer Bürgersupport"],
    )
    lhmExtId: str | None = Field(
        description="External ID from LHM",
        examples=[""],
    )


@broker.subscriber(
    settings.kafka.topic,
    group_id=settings.kafka.group_id,
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
