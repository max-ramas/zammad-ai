from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, CliSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict, YamlConfigSettingsSource


class Settings(BaseSettings):
    """
    Application settings for Zammad AI integration.
    """

    kafka: "KafkaSettings" = Field(
        default_factory=lambda: KafkaSettings(),
        description="Kafka related settings",
    )
    valid_request_types: list[str] = Field(
        default_factory=list,
        description="List of valid request types to be processed",
    )

    model_config = SettingsConfigDict(
        env_prefix="ZAMMAD_AI_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        env_nested_delimiter="__",
        nested_model_default_partial_update=True,
        yaml_file="config.yaml",
        yaml_file_encoding="utf-8",
        cli_parse_args=True,
        cli_kebab_case=True,
        cli_prog_name="zammad-ai",
    )

    # Reorder settings sources to prioritize YAML config
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            CliSettingsSource(settings_cls),
            env_settings,
            YamlConfigSettingsSource(settings_cls),
            dotenv_settings,
        )


class KafkaSettings(BaseModel):
    """
    Settings related to Kafka integration.
    """

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
    """Get cached application settings.

    Returns:
        Settings: The application settings.
    """
    return Settings()
