from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, FilePath


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

    security: MTLSKafkaEnvSecurity | MTLSFileKafkaSecurity | DisableKafkaSecurity = Field(
        default_factory=lambda: DisableKafkaSecurity(),
        description="Security configuration for Kafka connection.",
        discriminator="type",
    )


class DisableKafkaSecurity(BaseModel):
    """Explicitly disable Kafka security (e.g., for plaintext connections)."""

    type: Literal["none"] = Field(
        description="Discriminator for no-security configuration.",
        default="none",
    )


class MTLSKafkaEnvSecurity(BaseModel):
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


class MTLSFileKafkaSecurity(BaseModel):
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
