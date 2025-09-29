from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    kafka: "KafkaSettings" = Field(default_factory=lambda: KafkaSettings(), description="Kafka related settings")
    valid_request_types: list[str] = Field(default_factory=list, description="List of valid request types to be processed")


class KafkaSettings(BaseModel):
    broker_url: str = Field(
        description="URL of the Kafka message broker notifying ticket events",
        default="localhost:9092",
    )
    topic: str = Field(
        description="Kafka topic for ticket events",
        default="ticket-events",
    )
    group_id: str = Field(
        description="Kafka consumer group ID",
        default="zammad-ai",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
