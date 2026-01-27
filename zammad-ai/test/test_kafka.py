import pytest
from fastapi.exceptions import RequestValidationError
from faststream.kafka import TestKafkaBroker

from app.core.settings import KafkaSettings, Settings
from app.core.triage_settings import (
    Action,
    ActionRule,
    Category,
    LangfuseSettings,
    OpenAISettings,
    PromptConfig,
    QdrantSettings,
    TriageSettings,
    Usecase,
    ZammadSettings,
)
from app.kafka.broker import build_router

mock_settings = Settings(
    valid_request_types=["technischer Bürgersupport"],
    kafka=KafkaSettings(
        broker_url="localhost:9092",
        topic="test-ticket-events",
        group_id="test-consumer-group",
    ),
    triage=TriageSettings(
        usecase=Usecase(name="Test Usecase", description="Test usecase for unit testing"),
        categories=[
            Category(name="Test Category 1", id=1),
            Category(name="Test Category 2", id=2),
        ],
        no_category_id=999,
        actions=[
            Action(name="Test Action 1", description="First test action", id=1),
            Action(name="Test Action 2", description="Second test action", id=2),
        ],
        no_action_id=888,
        action_rules=[
            ActionRule(category_id=1, action_id=1, conditions=None),
        ],
        prompt_config=PromptConfig(
            label="test",
            categories_prompt="test/categories",
            examples_prompt="test/examples",
            role_prompt="test/role",
        ),
        openai=OpenAISettings(
            api_key="test-api-key",
            url="https://api.openai.com/v1",
            completions_model="gpt-4o-mini",
            embeddings_model="text-embedding-3-large",
            reasoning_effort="medium",
            temperature=0.7,
            max_retries=3,
        ),
        langfuse=LangfuseSettings(
            secret_key="test-secret-key",
            public_key="test-public-key",
            base_url="https://cloud.langfuse.com",
        ),
        zammad=ZammadSettings(
            base_url="https://test-zammad.example.com",
            auth_token="test-auth-token-abcdef",
            knowledge_base_id="42",
            rss_feed_token="test-rss-token",
        ),
        qdrant=QdrantSettings(
            host="https://test-qdrant.example.com",
            api_key="test-qdrant-api-key",
            collection_name="test-collection",
            vector_name="test-vector",
            vector_dimension=1536,
        ),
    ),
)


@pytest.fixture
def valid_message() -> dict:
    """Standard valid test message."""
    return {
        "action": "created",
        "ticket": "3720",
        "status": "new",
        "statusId": "1",
        "anliegenart": "technischer Bürgersupport",
        "lhmExtId": "",
    }


@pytest.mark.asyncio
async def test_event_handler_valid_message(valid_message: dict) -> None:
    """Test event handler with a valid message."""
    settings = Settings(valid_request_types=["technischer Bürgersupport"])
    router, event_handler = build_router(settings=settings)
    async with TestKafkaBroker(router.broker) as test_broker:
        # copy fixture to avoid mutating the shared dict if a test modifies it
        message = dict(valid_message)
        await test_broker.publish(topic=settings.kafka.topic, message=message)
        event_handler.mock.assert_called_once_with(message)  # type: ignore


@pytest.mark.asyncio
async def test_event_handler_with_requestType_alias(valid_message: dict) -> None:
    """Test event handler accepts requestType as alias for anliegenart."""
    settings = Settings(valid_request_types=["technischer Bürgersupport"])
    router, event_handler = build_router(settings=settings)
    async with TestKafkaBroker(router.broker) as test_broker:
        message = dict(valid_message)
        # Use alias instead of anliegenart
        message.pop("anliegenart", None)
        message["requestType"] = "technischer Bürgersupport"
        await test_broker.publish(topic=settings.kafka.topic, message=message)
        event_handler.mock.assert_called_once_with(message)  # type: ignore


@pytest.mark.asyncio
async def test_event_handler_invalid_request_type(valid_message: dict, caplog) -> None:
    """Test event handler skips messages with invalid request types."""
    settings = Settings(valid_request_types=["technischer Bürgersupport"])
    router, event_handler = build_router(settings=settings)
    async with TestKafkaBroker(router.broker) as test_broker:
        message = dict(valid_message)
        message["anliegenart"] = "invalid_request_type"
        with caplog.at_level("INFO"):
            await test_broker.publish(topic=settings.kafka.topic, message=message)
        assert "Skipping" in caplog.text


@pytest.mark.asyncio
async def test_event_handler_invalid_message_format() -> None:
    """Test event handler with malformed message that fails Pydantic validation."""
    settings = Settings(valid_request_types=["technischer Bürgersupport"])
    router, event_handler = build_router(settings=settings)
    async with TestKafkaBroker(router.broker) as test_broker:
        # Missing required fields
        invalid_message: dict = {
            "action": "created",
            # Missing required fields: ticket, status, statusId, request_type
        }
        with pytest.raises(expected_exception=RequestValidationError):
            await test_broker.publish(topic=settings.kafka.topic, message=invalid_message)


@pytest.mark.asyncio
async def test_event_handler_with_multiple_valid_request_types(valid_message: dict) -> None:
    """Test event handler with multiple valid request types configured."""
    settings = Settings(valid_request_types=["technischer Bürgersupport", "general support", "other"])
    router, event_handler = build_router(settings=settings)
    async with TestKafkaBroker(router.broker) as test_broker:
        message = dict(valid_message)
        message["anliegenart"] = "general support"
        await test_broker.publish(topic=settings.kafka.topic, message=message)
        event_handler.mock.assert_called_once_with(message)  # type: ignore


@pytest.mark.asyncio
async def test_event_handler_case_sensitive_request_type(valid_message: dict, caplog) -> None:
    """Test that request type validation is case sensitive."""
    settings = Settings(
        valid_request_types=["technischer Bürgersupport"]  # exact case
    )
    router, event_handler = build_router(settings=settings)
    async with TestKafkaBroker(router.broker) as test_broker:
        message = dict(valid_message)
        message["anliegenart"] = "TECHNISCHER BÜRGERSUPPORT"  # Different case
        with caplog.at_level("INFO"):
            await test_broker.publish(topic=settings.kafka.topic, message=message)
        assert "Skipping event" in caplog.text
