from __future__ import annotations

from abc import ABC
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FilePath


class KafkaSettings(BaseModel):
    """

    Settings related to Kafka integration.
    """

    broker_url: str = Field(
        description="URL of the Kafka message broker notifying ticket events.",
        default="localhost:9092",
    )

    topic: str = Field(
        description="Kafka topic for ticket events",
        default="ticket-events",
    )

    group_id: str | None = Field(
        description="Kafka consumer group ID",
        default=None,
    )

    security: (
        Annotated[
            KafkaMTLSEnvSecurity | KafkaMTLSFileSecurity,
            Field(discriminator="type"),
        ]
        | None
    ) = Field(
        default=None,
        description="Security configuration for Kafka connection.",
    )


class KafkaSecurity(BaseModel, ABC):
    """Base class for Kafka security configurations."""

    model_config = ConfigDict(extra="forbid")


class KafkaMTLSEnvSecurity(KafkaSecurity):
    """mTLS configuration for Kafka connection using environment variables only."""

    type: Literal["env"] = Field(
        description="Discriminator for environment-based mTLS configuration.",
        default="env",
    )

    ca_file_base64: str = Field(
        description="Base64-encoded CA certificate.",
    )

    pkcs12_base64: str = Field(
        description="Base64-encoded PKCS#12 payload.",
    )

    pkcs12_pw_base64: str = Field(
        description="Base64-encoded PKCS#12 password.",
    )


class KafkaMTLSFileSecurity(KafkaSecurity):
    """mTLS configuration for Kafka connection using file paths."""

    type: Literal["file"] = Field(
        description="Discriminator for file-based mTLS configuration.",
        default="file",
    )

    ca_file_path: FilePath = Field(
        description="Path to the CA certificate file (PEM format).",
    )

    client_cert_path: FilePath = Field(
        description="Path to the client certificate file (PEM format).",
    )

    client_key_path: FilePath = Field(
        description="Path to the client private key file (PEM format).",
    )
