# Zammad-AI

[![Made with love by it@M][made-with-love-shield]][itm-opensource]

**GenAI-powered agent for Zammad**

Zammad-AI is a Python-based microservice that integrates Generative AI capabilities into the Zammad ticketing system. It operates as an event-driven service, listening to ticket events via Kafka and generating AI-assisted responses.

## 🚀 Features

- **Event-Driven Architecture**: Built with [FastStream](https://faststream.airt.ai/) and Kafka for robust message processing.
- **AI-Powered Triage**: Classifies tickets and applies automated actions based on configurable rules.
- **Vector Database Support**: Uses [Qdrant](https://qdrant.tech/) for knowledge retrieval via semantic search.
- **Full Observability**: Integration with [Langfuse](https://langfuse.com/) for tracing, cost monitoring, and dynamic prompt management.
- **Zammad Integration**: Supports both REST API and custom EAI integration paths.
- **Secure Communication**: Supports mTLS for secure Kafka connections using `truststore`.
- **Modern Stack**: Powered by Python 3.13, Pydantic, and LangChain.

## 📖 Documentation

Detailed documentation is available in the `docs/` folder:

- **[Architecture (ADRs)](docs/adr/index.md)**: Explore the technical decisions and system design.
- **[Software Components](docs/components/index.md)**: Details on Kafka, Triage, Zammad integration, and Qdrant.
- **[Configuration Guide](docs/configuration.md)**: How to set up the service and manage secrets.
- **[REST API Reference](docs/api.md)**: Documentation for the FastAPI endpoints.

## 🛠️ Architecture

1.  **Ingest**: Listens to the Kafka topic or receives synchronous REST API requests.
2.  **Triage**: Analyzes input using GenAI to determine category, reasoning, and next steps.
3.  **Action**: Evaluates triggers (conditions) to execute specific tasks (e.g., generate a response).
4.  **Integration**: Interacts with Zammad to fetch ticket context or post final results.

## 📋 Prerequisites

- **Python**: 3.13+
- **Package Manager**: [uv](https://github.com/astral-sh/uv)
- **Docker**: For running the local development stack.

## ⚙️ Configuration

The service is highly configurable via YAML, environment variables, and `.env` files. For a full list of settings and examples, please refer to the **[Configuration Guide](docs/configuration.md)**.

### Quick Start Settings

| Setting               | Env Variable                    | Description                 | Default          |
| :-------------------- | :------------------------------ | :-------------------------- | :--------------- |
| `kafka.broker_url`    | `ZAMMAD_AI_KAFKA__BROKER_URL`   | Kafka broker URL            | `localhost:9092` |
| `kafka.topic`         | `ZAMMAD_AI_KAFKA__TOPIC`        | Kafka topic to listen to    | `ticket-events`  |
| `valid_request_types` | `ZAMMAD_AI_VALID_REQUEST_TYPES` | List of valid request types | _Required_       |

Example `config.yaml`:

```yaml
kafka:
  broker_url: "localhost:9092"
  topic: "ticket-events"

valid_request_types:
  - "general_inquiry"
  - "support"
```

## 🏃‍♂️ Running Locally

### 1. Start Infrastructure

Start the local Kafka broker, Zookeeper, and Mailpit using Docker Compose:

```bash
docker compose up -d
```

- **Kafka UI**: http://localhost:8089
- **Mailpit**: http://localhost:8025

### 2. Install Dependencies

Use `uv` to install the project dependencies:

```bash
uv sync
```

### 3. Run the Service

Run the application:

```bash
uv run python zammad-ai/main.py
```

### 4. Optional: Enable Embedded Frontend

The service can mount a Gradio frontend at `/` for local developer workflows.

In `zammad-ai/config.yaml`:

```yaml
frontend:
  enabled: true
  request_timeout_seconds: 30.0
  auth_username: "admin"
  auth_password: "change-me"
```

Then start the service and open:

- Frontend UI: `http://localhost:8080/`
- OpenAPI docs (development mode): `http://localhost:8080/api/docs`

When frontend mode is enabled, basic auth is required. 

## 🧪 Testing

Run the test suite using `pytest`:

```bash
uv run pytest
```

## 💻 Development

### Linting & Formatting

The project uses `ruff` for linting and formatting.

Check for issues:

```bash
uv run ruff check .
```

Format code:

```bash
uv run ruff format .
```

## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please open an issue with the tag "enhancement", fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Open an issue with the tag "enhancement"
2. Fork the Project
3. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
4. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
5. Push to the Branch (`git push origin feature/AmazingFeature`)
6. Open a Pull Request

More about this in the [CODE_OF_CONDUCT](/CODE_OF_CONDUCT.md) file.

## License

Distributed under the MIT License. See [LICENSE](LICENSE) file for more information.

## Contact

it@M - opensource@muenchen.de

<!-- project shields / links -->

[made-with-love-shield]: https://img.shields.io/badge/made%20with%20%E2%9D%A4%20by-it%40M-yellow?style=for-the-badge
[itm-opensource]: https://opensource.muenchen.de/
