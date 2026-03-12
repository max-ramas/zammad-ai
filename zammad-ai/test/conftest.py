"""Shared pytest fixtures for unit tests.

This module centralizes test setup for settings, logging, global state cleanup,
Kafka payloads, and reusable fake dependencies.
"""

import logging
import os
from collections.abc import Callable, Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from faststream.kafka import TestKafkaBroker
from pydantic import HttpUrl, SecretStr

from app.settings import GenAISettings, KafkaSettings, TriageSettings, ZammadAISettings, ZammadAPISettings
from app.settings.triage import Action, ActionRule, Category, StringTriagePrompts
from test.fakes import FakeGenAIHandler, FakeLangfuseClient, FakeZammadClient

_TEST_ENV_DEFAULTS: dict[str, str] = {
    "ZAMMAD_AI_MODE": "unittest",
    "ZAMMAD_AI_DISABLE_YAML": "1",
    "ZAMMAD_AI_LANGFUSE_ENABLED": "false",
    "ZAMMAD_AI_ZAMMAD__TYPE": "api",
    "ZAMMAD_AI_ZAMMAD__BASE_URL": "https://example.com",
    "ZAMMAD_AI_ZAMMAD__AUTH_TOKEN": "test-token",
    "ZAMMAD_AI_TRIAGE": '{"categories":[{"name":"Unknown","id":0}],"no_category_id":0,"actions":[{"name":"Default","description":"Default","id":1}],"no_action_id":1,"action_rules":[],"prompts":{"type":"string","categories":"List of categories: {{categories}}","examples":"Examples: {{examples}}","role":"You are a helpful assistant that categorizes support requests into the above categories based on the content of the request."}}',
    "ZAMMAD_AI_VALID_REQUEST_TYPES": '["support"]',
    "ZAMMAD_AI_QDRANT__API_KEY": "test-key",
}

DEFAULT_GENAI_PROMPTS = {
    "categories": "List of categories: {{categories}}",
    "examples": "Examples: {{examples}}",
    "role": "You are a helpful assistant that categorizes support requests into the above categories based on the content of the request.",
}


class _ApiTriageStub:
    def __init__(self) -> None:
        self.no_category = Category(name="Unknown", id=0)
        self.no_action = Action(name="Default", description="Default", id=1)

    async def predict_category(self, *_args, **_kwargs) -> Any:
        from app.models.triage import CategorizationResult

        return CategorizationResult(category=self.no_category, reasoning="stub", confidence=1.0)

    async def get_action_id(self, *_args, **_kwargs) -> int:
        return self.no_action.id

    def _id_to_action(self, _action_id: int) -> Action:
        return self.no_action

    async def cleanup(self) -> None:
        return None


def pytest_configure() -> None:
    """Set deterministic environment defaults for all tests."""
    for key, value in _TEST_ENV_DEFAULTS.items():
        os.environ.setdefault(key, value)


@pytest.fixture(scope="session")
def base_settings() -> ZammadAISettings:
    """Provide one minimal valid settings object for reuse across tests."""
    return ZammadAISettings.model_construct(
        mode="unittest",
        langfuse_enabled=False,
        genai=GenAISettings(),
        zammad=ZammadAPISettings(
            base_url=HttpUrl(url="https://example.com"),
            auth_token=SecretStr(secret_value="test-token"),
        ),
        kafka=KafkaSettings(
            broker_url="localhost:9092",
            group_id="test-group",
            topic="test-topic",
        ),
        triage=TriageSettings.model_construct(
            categories=[Category(name="Unknown", id=0), Category(name="General", id=1)],
            no_category_id=0,
            actions=[Action(name="Default", description="Default", id=1), Action(name="Escalate", description="Escalate", id=3)],
            no_action_id=1,
            action_rules=[],
            prompts=StringTriagePrompts(
                type="string",
                categories=DEFAULT_GENAI_PROMPTS["categories"],
                examples=DEFAULT_GENAI_PROMPTS["examples"],
                role=DEFAULT_GENAI_PROMPTS["role"],
            ),
        ),
        valid_request_types=["support", "technischer Bürgersupport"],
    )


@pytest.fixture
def settings_factory(base_settings: ZammadAISettings) -> Callable[..., ZammadAISettings]:
    """Return a factory for test settings with optional overrides."""

    def _factory(
        *,
        action_rules: list[ActionRule] | None = None,
        valid_request_types: list[str] | None = None,
        **overrides: Any,
    ) -> ZammadAISettings:
        settings = base_settings.model_copy(deep=True)
        if action_rules is not None:
            settings.triage.action_rules = action_rules
        if valid_request_types is not None:
            settings.valid_request_types = valid_request_types
        if overrides:
            settings = settings.model_copy(update=overrides, deep=True)
        return settings

    return _factory


@pytest.fixture(autouse=True)
def cleanup_settings_cache() -> Generator[None, None, None]:
    """Reset cached settings before and after each test."""
    from app.settings.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def cleanup_log_config_cache() -> Generator[None, None, None]:
    """Reset cached logging configuration before and after each test."""
    from app.utils.logging import get_log_config

    get_log_config.cache_clear()
    yield
    get_log_config.cache_clear()


@pytest.fixture(autouse=True)
def cleanup_triage_singleton() -> Generator[None, None, None]:
    """Reset shared triage singleton to prevent test pollution."""
    import app.triage.triage as triage_module

    triage_module._triage = None
    yield
    triage_module._triage = None


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch: pytest.MonkeyPatch, settings_factory: Callable[..., ZammadAISettings]) -> ZammadAISettings:
    """Patch get_settings() to return deterministic test settings."""
    settings = settings_factory()
    monkeypatch.setattr("app.settings.settings.get_settings", lambda: settings)
    monkeypatch.setattr("app.settings.get_settings", lambda: settings)
    return settings


@pytest.fixture
def mock_logger(monkeypatch: pytest.MonkeyPatch) -> logging.Logger:
    """Provide a preconfigured logger and bypass logging setup I/O in tests."""
    logger = logging.getLogger("zammad-ai.tests")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    monkeypatch.setattr("app.utils.logging.getLogger", lambda _name="zammad-ai": logger)
    return logger


@pytest.fixture
def temp_logconf(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Create a temporary log configuration file for tests needing one."""
    path = tmp_path_factory.mktemp("logconf") / "logconf.yaml"
    path.write_text(
        """
version: 1
formatters:
  simple:
    format: '%(levelname)s %(name)s %(message)s'
handlers:
  console:
    class: logging.StreamHandler
    formatter: simple
    stream: ext://sys.stdout
loggers:
  zammad-ai:
    level: INFO
    handlers: [console]
    propagate: false
root:
  level: INFO
  handlers: [console]
""".strip(),
        encoding="utf-8",
    )
    return str(path)


@pytest.fixture
def kafka_message_factory() -> Callable[..., dict[str, str]]:
    """Create valid Kafka payloads with optional field overrides."""

    def _factory(**overrides: str) -> dict[str, str]:
        payload = {
            "action": "created",
            "ticket": "3720",
            "status": "new",
            "statusId": "1",
            "anliegenart": "technischer Bürgersupport",
            "lhmExtId": "",
        }
        payload.update(overrides)
        return payload

    return _factory


@pytest.fixture
def valid_message(kafka_message_factory: Callable[..., dict[str, str]]) -> dict[str, str]:
    """Backward-compatible valid Kafka message fixture."""
    return kafka_message_factory()


@pytest.fixture
def test_kafka_broker() -> Callable[[Any], TestKafkaBroker]:
    """Create FastStream TestKafkaBroker instances for a router."""

    def _factory(router: Any) -> TestKafkaBroker:
        return TestKafkaBroker(router.broker)

    return _factory


@pytest.fixture
def fake_langfuse_client() -> FakeLangfuseClient:
    """Return a fake Langfuse client."""
    return FakeLangfuseClient()


@pytest.fixture
def fake_genai_handler() -> FakeGenAIHandler:
    """Return a fake GenAI handler with default prompts."""

    return FakeGenAIHandler(
        genai_settings=GenAISettings(),
        prompts=DEFAULT_GENAI_PROMPTS,
    )


@pytest.fixture
def fake_zammad_client(settings_factory: Callable[..., ZammadAISettings]) -> FakeZammadClient:
    """Return a fake Zammad API client."""
    settings = settings_factory()
    assert isinstance(settings.zammad, ZammadAPISettings)
    return FakeZammadClient(settings=settings.zammad)


@pytest.fixture
def test_client(monkeypatch: pytest.MonkeyPatch, settings_factory: Callable[..., ZammadAISettings]) -> Generator[TestClient, None, None]:
    """Provide a FastAPI TestClient with patched settings and triage dependencies."""
    import importlib

    settings = settings_factory()
    triage_stub = _ApiTriageStub()

    monkeypatch.setattr("app.settings.settings.get_settings", lambda: settings)
    monkeypatch.setattr("app.settings.get_settings", lambda: settings)

    import app.api.backend as backend_module

    backend_module = importlib.reload(backend_module)  # type: ignore
    monkeypatch.setattr(backend_module, "get_triage", lambda settings=None: triage_stub)

    with TestClient(backend_module.backend) as client:
        yield client
