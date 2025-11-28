# Zammad-AI Copilot Instructions

## Project Overview

Zammad-AI is a Python-based service that integrates GenAI capabilities into the Zammad ticketing system. It operates as a Kafka consumer, reacting to ticket events to provide AI-assisted responses.

## Architecture & Core Concepts

- **Service Type**: Event-driven microservice using `FastStream` with Kafka.
- **Data Flow**:
  1.  **Ingest**: Listens to `ticket-events` Kafka topic.
  2.  **Filter**: Validates events based on `request_type` (mapped from `anliegenart`).
  3.  **Process**: (Future) Fetches ticket details via Zammad API, generates AI response.
  4.  **Output**: (Future) Posts draft response back to Zammad.
- **Configuration**: Managed via `pydantic-settings` in `app/core/settings.py`. Supports `config.yaml`, `.env`, and environment variables (prefix `ZAMMAD_AI_`).
- **Security**: Supports mTLS for Kafka connections using `truststore` and `cryptography`.

## Developer Workflows

### Dependency Management

- Uses `uv` for package management.
- `pyproject.toml` defines dependencies.

### Running the Application

- **Local Dev Stack**: `docker compose up -d` starts Kafka, Zookeeper, Kafka UI (port 8089), and Mailpit.
- **Start Service**: Run `python zammad-ai/main.py`.
  - Loads environment variables from `.env`.
  - Connects to Kafka broker (default `localhost:9092`).

### Testing

- **Framework**: `pytest` with `pytest-asyncio`.
- **Kafka Testing**: Use `faststream.kafka.TestKafkaBroker` for in-memory broker testing.
  - **Pattern**:
    ```python
    async with TestKafkaBroker(broker) as test_broker:
        await test_broker.publish(topic=settings.kafka.topic, message=message)
        # Assertions
    ```
- **Location**: Tests are in `zammad-ai/test/`.

### Linting & Formatting

- **Tool**: `ruff`.
- **Config**: `ruff.toml` in root.

## Code Conventions & Patterns

### Kafka Integration

- **Broker Setup**: Defined in `app/kafka/broker.py`.
- **Event Handling**: Decorate functions with `@broker.subscriber`.
- **Message Validation**: Use Pydantic models (e.g., `Event` in `app/models/kafka.py`).
- **Ack Policy**: Explicitly handle `AckMessage` and `NackMessage`.

### Configuration

- **Access**: Use `app.core.settings.get_settings()`.
- **Structure**: Nested models (e.g., `KafkaSettings`) for logical grouping.
- **Overrides**: YAML config takes precedence over `.env`, but CLI args and Env Vars override YAML.

### Logging

- **Logger**: Use `app.utils.logging.getLogger("zammad-ai")`.
- **Pattern**:
  ```python
  from app.utils.logging import getLogger
  logger = getLogger("zammad-ai")
  logger.info("Message")
  ```

## Key Files

- `zammad-ai/main.py`: Application entry point.
- `zammad-ai/app/kafka/broker.py`: Kafka broker configuration and event handlers.
- `zammad-ai/app/core/settings.py`: Configuration definitions.
- `zammad-ai/test/test_kafka.py`: Example of Kafka consumer testing.
- `compose.yaml`: Infrastructure definition.
