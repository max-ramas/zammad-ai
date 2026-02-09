from __future__ import annotations

from collections.abc import Generator

import pytest

from app.core.settings import ZammadAISettings
from app.core.settings.genai import GenAISettings
from app.core.settings.kafka import KafkaSettings
from app.core.settings.qdrant import QdrantSettings
from app.core.settings.triage import (
    Action,
    ActionRule,
    Category,
    Condition,
    StringTriagePrompts,
    TriageSettings,
)
from app.core.settings.zammad import ZammadAPISettings
from app.models.triage import CategorizationResult, DaysSinceRequestResponse, ProcessingIdResponse
from app.models.zammad import ZammadArticle, ZammadTicket
from app.triage import triage as triage_module
from app.triage.triage import Triage, TriageError
from app.zammad.base import ZammadConnectionError


class FakeLangfuseClient:
    def generate_session_id(self) -> str:
        """
        Return a fixed session identifier for the fake Langfuse client.

        Returns:
            session_id (str): The constant session identifier "session-id".
        """
        return "session-id"


class FakeGenAIHandler:
    def __init__(self, genai_settings: GenAISettings, prompts: dict[str, str]) -> None:
        """
        Initialize the fake GenAI handler with settings and prompt templates, and prepare default response placeholders.

        Parameters:
                genai_settings (GenAISettings): Configuration for GenAI behavior (kept for parity with real handler).
                prompts (dict[str, str]): Mapping of prompt names to prompt text used by the handler.
        """
        self.prompts = prompts
        self.langfuse_client = FakeLangfuseClient()
        self.categorization_result: CategorizationResult | None = None
        self.days_since_request_response: DaysSinceRequestResponse | None = None
        self.processing_id_response: ProcessingIdResponse | None = None

    async def predict_category(self, input: dict, session_id: str | None = None) -> CategorizationResult:
        """
        Return a preset categorization result or a default "no result" CategorizationResult.

        Parameters:
            input (dict): The input payload to be categorized.
            session_id (str | None): Optional session identifier for tracing.

        Returns:
            CategorizationResult: The configured `categorization_result` if present; otherwise a result with
            `category=None`, `reasoning="no result"`, and `confidence=0.0`.
        """
        if self.categorization_result is None:
            return CategorizationResult(
                category=None,
                reasoning="no result",
                confidence=0.0,
            )
        return self.categorization_result

    async def extract_days_since_request(self, input: dict, session_id: str | None = None) -> DaysSinceRequestResponse:
        """
        Return the preset days-since-request response if available; otherwise return a default response with days_since_request set to 0 and reason "default".

        Parameters:
            input (dict): Input payload to extract days-since-request from.
            session_id (str | None): Optional session identifier (may be unused by this fake handler).

        Returns:
            DaysSinceRequestResponse: The configured or default days-since-request response.
        """
        if self.days_since_request_response is None:
            return DaysSinceRequestResponse(days_since_request=0, reason="default")
        return self.days_since_request_response

    async def extract_processing_id(self, input: dict, session_id: str | None = None) -> ProcessingIdResponse:
        """
        Extracts a processing identifier and whether its associated condition was met from the provided input.

        Parameters:
            input (dict): The parsed input data used to derive the processing identifier.
            session_id (str | None): Optional session identifier for tracing; not required for extraction.

        Returns:
            ProcessingIdResponse: Contains `processing_id` (empty string when none) and `condition_met` (`True` if the condition was met, `False` otherwise).
        """
        if self.processing_id_response is None:
            return ProcessingIdResponse(processing_id="", condition_met=False)
        return self.processing_id_response


class FakeZammadClient:
    def __init__(self, settings: ZammadAPISettings) -> None:
        """
        Create a fake Zammad API client configured with the provided Zammad API settings.

        Parameters:
            settings (ZammadAPISettings): Configuration used by the fake client.

        Description:
            Initializes the client's settings and sets `ticket` to `None` to indicate no preset ticket.
        """
        self.settings = settings
        self.ticket: ZammadTicket | None = None
        self.raise_connection_error: bool = False

    async def get_ticket(self, id: str) -> ZammadTicket:
        """
        Retrieve a ticket by id from the fake client, returning a preset ticket or a default empty ticket.

        Parameters:
            id (str): The ticket identifier to retrieve.

        Returns:
            ZammadTicket: The preset ticket if one is stored on the client; otherwise a ZammadTicket with the given `id` and an empty `articles` list.

        Raises:
            ZammadConnectionError: If ``raise_connection_error`` is set to ``True``.
        """
        if self.raise_connection_error:
            raise ZammadConnectionError("Fake connection error")
        if self.ticket is None:
            return ZammadTicket(id=id, articles=[])
        return self.ticket

    async def post_answer(self, ticket_id: str, text: str, internal: bool = False) -> None:
        """
        Test stub that fails if a call to post_answer occurs during tests.

        Raises:
            AssertionError: Always raised to indicate this method must not be invoked in the test context.
        """
        raise AssertionError("post_answer should not be called in these tests")

    async def post_shared_draft(self, ticket_id: str, text: str) -> None:
        """
        Fail the test if posting a shared draft is attempted.

        This test stub always raises an AssertionError to ensure posting a shared draft is not invoked during unit tests.

        Raises:
            AssertionError: Always raised to indicate the method must not be called in tests.
        """
        raise AssertionError("post_shared_draft should not be called in these tests")

    async def add_tag_to_ticket(self, ticket_id: str, tag: str) -> None:
        """
        Prevent adding a tag to a ticket during tests by failing if invoked.

        Parameters:
            ticket_id (str): ID of the ticket that would receive the tag.
            tag (str): Tag that would be added to the ticket.

        Raises:
            AssertionError: Always raised to indicate this method must not be called in tests.
        """
        raise AssertionError("add_tag_to_ticket should not be called in these tests")


def create_mock_settings(action_rules: list[ActionRule] | None = None) -> ZammadAISettings:
    """
    Constructs a ZammadAISettings instance populated with test-oriented defaults for unit tests.

    Parameters:
        action_rules (list[ActionRule] | None): Optional list of ActionRule objects to include in the triage settings; if None, an empty list is used.

    Returns:
        ZammadAISettings: A settings object with prefilled test values (mode "unittest"), default GenAI and Zammad API settings, Qdrant and Kafka test configuration, triage settings including two categories ("Unknown", "General"), two actions ("Default", "Escalate"), the provided or empty action_rules, default prompts, valid_request_types set to ["support"], and langfuse_enabled set to True.
    """
    import sys

    original_argv = sys.argv
    try:
        sys.argv = ["zammad-ai"]
        return ZammadAISettings.model_construct(
            mode="unittest",
            genai=GenAISettings(),
            zammad=ZammadAPISettings(
                base_url="https://example.com",  # type: ignore
                auth_token="test-token",  # type: ignore
            ),
            qdrant=QdrantSettings(
                host="https://qdrant.example.com",  # type: ignore
                api_key="test-key",  # type: ignore
                collection_name="test_collection",
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
                action_rules=action_rules or [],
                prompts=StringTriagePrompts(),
            ),
            valid_request_types=["support"],
            langfuse_enabled=True,
        )
    finally:
        sys.argv = original_argv


@pytest.fixture
def patched_triage(monkeypatch: pytest.MonkeyPatch) -> Generator[Triage, None, None]:
    """
    Provide a Triage instance with external dependencies replaced by test fakes.

    Parameters:
        monkeypatch (pytest.MonkeyPatch): Pytest monkeypatch fixture used to replace GenAIHandler and ZammadAPIClient in the triage module.

    Returns:
        Generator[Triage, None, None]: Yields a Triage instance configured with mock settings and using FakeGenAIHandler and FakeZammadClient.
    """
    monkeypatch.setattr(triage_module, "GenAIHandler", FakeGenAIHandler)
    monkeypatch.setattr(triage_module, "ZammadAPIClient", FakeZammadClient)
    settings = create_mock_settings()
    triage = Triage(settings=settings)
    yield triage


@pytest.mark.asyncio
async def test_perform_triage_returns_defaults_when_no_articles(patched_triage: Triage) -> None:
    result = await patched_triage.perform_triage(id="123")
    assert result.category == patched_triage.no_category
    assert result.action == patched_triage.no_action
    assert result.reasoning == "Keine Artikel gefunden"
    assert result.confidence == 1.0


@pytest.mark.asyncio
async def test_predict_category_falls_back_to_no_category(patched_triage: Triage) -> None:
    patched_triage.genai_handler.categorization_result = CategorizationResult(  # type: ignore
        category=Category(name="Unknown", id=999),
        reasoning="mismatch",
        confidence=0.42,
    )
    result = await patched_triage.predict_category(message="some text", session_id="session-id")
    assert result.category == patched_triage.no_category
    assert "no_category" in result.reasoning
    assert result.confidence == 1.0


@pytest.mark.asyncio
async def test_get_action_id_uses_days_since_request_condition(monkeypatch: pytest.MonkeyPatch) -> None:
    action_rules = [
        ActionRule(
            category_id=1,
            action_id=1,
            conditions=[
                Condition(
                    priority=1,
                    field="days_since_request",
                    operator="greater_equals",
                    value=10,
                    action_id=3,
                )
            ],
        )
    ]
    monkeypatch.setattr(triage_module, "GenAIHandler", FakeGenAIHandler)
    monkeypatch.setattr(triage_module, "ZammadAPIClient", FakeZammadClient)
    settings = create_mock_settings(action_rules=action_rules)
    triage = Triage(settings=settings)
    triage.genai_handler.days_since_request_response = DaysSinceRequestResponse(days_since_request=12, reason="ok")  # type: ignore
    categorization = CategorizationResult(
        category=Category(name="General", id=1),
        reasoning="ok",
        confidence=0.8,
    )

    action_id = await triage.get_action_id(categorization_result=categorization, message="message", session_id="session-id")

    assert action_id == 3


@pytest.mark.asyncio
async def test_get_action_id_returns_no_action_for_no_category(patched_triage: Triage) -> None:
    categorization = CategorizationResult(
        category=patched_triage.no_category,
        reasoning="no category",
        confidence=1.0,
    )

    action_id = await patched_triage.get_action_id(categorization_result=categorization, message="message", session_id="session-id")

    assert action_id == patched_triage.no_action.id


# ---------------------------------------------------------------------------
# perform_triage: happy path with articles
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_perform_triage_happy_path(patched_triage: Triage) -> None:
    """Full triage with a ticket that has an article returns a real category and action."""
    patched_triage.zammad_client.ticket = ZammadTicket(  # type: ignore
        id="42",
        articles=[ZammadArticle(id="1", ticket_id="42", text="My printer is broken")],
    )
    patched_triage.genai_handler.categorization_result = CategorizationResult(  # type: ignore
        category=Category(name="General", id=1),
        reasoning="hardware issue",
        confidence=0.9,
    )
    result = await patched_triage.perform_triage(id="42")
    assert result.category.id == 1
    assert result.reasoning == "hardware issue"
    assert result.confidence == 0.9


# ---------------------------------------------------------------------------
# perform_triage: Zammad connection error → TriageError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_perform_triage_raises_triage_error_on_zammad_failure(patched_triage: Triage) -> None:
    """A Zammad connection error should be wrapped in TriageError."""
    patched_triage.zammad_client.raise_connection_error = True  # type: ignore
    with pytest.raises(TriageError, match="Zammad connection error"):
        await patched_triage.perform_triage(id="99")


# ---------------------------------------------------------------------------
# predict_category: empty message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_predict_category_empty_message(patched_triage: Triage) -> None:
    """An empty (or whitespace-only) message returns no_category immediately."""
    result = await patched_triage.predict_category(message="   ", session_id="session-id")
    assert result.category == patched_triage.no_category
    assert "Leere Nachricht" in result.reasoning
    assert result.confidence == 1.0


# ---------------------------------------------------------------------------
# predict_category: valid category keeps the prediction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_predict_category_valid_category_kept(patched_triage: Triage) -> None:
    """A valid category returned by GenAI is kept as-is."""
    patched_triage.genai_handler.categorization_result = CategorizationResult(  # type: ignore
        category=Category(name="General", id=1),
        reasoning="looks right",
        confidence=0.88,
    )
    result = await patched_triage.predict_category(message="some text", session_id="session-id")
    assert result.category.id == 1
    assert result.reasoning == "looks right"
    assert result.confidence == 0.88


# ---------------------------------------------------------------------------
# predict_category: GenAI handler raises → graceful fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_predict_category_handles_genai_exception(patched_triage: Triage) -> None:
    """An unexpected exception from the GenAI handler is caught and returns no_category."""

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("LLM exploded")

    patched_triage.genai_handler.predict_category = _boom  # type: ignore
    result = await patched_triage.predict_category(message="trigger error", session_id="session-id")
    assert result.category == patched_triage.no_category
    assert "Unerwarteter Fehler" in result.reasoning
    assert result.confidence == 1.0


# ---------------------------------------------------------------------------
# get_action_id: rule match without conditions → use rule's action_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_action_id_rule_without_conditions(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rule with no conditions directly returns the rule's action_id."""
    action_rules = [
        ActionRule(category_id=1, action_id=3, conditions=None),
    ]
    monkeypatch.setattr(triage_module, "GenAIHandler", FakeGenAIHandler)
    monkeypatch.setattr(triage_module, "ZammadAPIClient", FakeZammadClient)
    settings = create_mock_settings(action_rules=action_rules)
    triage = Triage(settings=settings)
    categorization = CategorizationResult(
        category=Category(name="General", id=1),
        reasoning="ok",
        confidence=0.8,
    )

    action_id = await triage.get_action_id(categorization_result=categorization, message="msg", session_id="s")
    assert action_id == 3


# ---------------------------------------------------------------------------
# get_action_id: condition NOT met → falls through to rule's default action_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_action_id_condition_not_met_falls_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """When a condition's operator check fails, the rule's default action_id is returned."""
    action_rules = [
        ActionRule(
            category_id=1,
            action_id=1,
            conditions=[
                Condition(priority=1, field="days_since_request", operator="greater_equals", value=10, action_id=3),
            ],
        ),
    ]
    monkeypatch.setattr(triage_module, "GenAIHandler", FakeGenAIHandler)
    monkeypatch.setattr(triage_module, "ZammadAPIClient", FakeZammadClient)
    settings = create_mock_settings(action_rules=action_rules)
    triage = Triage(settings=settings)
    # days=5 does NOT satisfy >=10
    triage.genai_handler.days_since_request_response = DaysSinceRequestResponse(days_since_request=5, reason="recent")  # type: ignore
    categorization = CategorizationResult(category=Category(name="General", id=1), reasoning="ok", confidence=0.8)

    action_id = await triage.get_action_id(categorization_result=categorization, message="msg", session_id="s")
    assert action_id == 1  # rule's default, not the condition's action_id


# ---------------------------------------------------------------------------
# get_action_id: processing_id condition match
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_action_id_processing_id_condition(monkeypatch: pytest.MonkeyPatch) -> None:
    """A processing_id condition that matches returns the condition's action_id."""
    action_rules = [
        ActionRule(
            category_id=1,
            action_id=1,
            conditions=[
                Condition(priority=1, field="processing_id", operator="equals", value="ABC", action_id=3),
            ],
        ),
    ]
    monkeypatch.setattr(triage_module, "GenAIHandler", FakeGenAIHandler)
    monkeypatch.setattr(triage_module, "ZammadAPIClient", FakeZammadClient)
    settings = create_mock_settings(action_rules=action_rules)
    triage = Triage(settings=settings)
    triage.genai_handler.processing_id_response = ProcessingIdResponse(processing_id="ABC", condition_met=True)  # type: ignore
    categorization = CategorizationResult(category=Category(name="General", id=1), reasoning="ok", confidence=0.8)

    action_id = await triage.get_action_id(categorization_result=categorization, message="msg", session_id="s")
    assert action_id == 3


# ---------------------------------------------------------------------------
# get_action_id: no matching rule → no_action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_action_id_no_matching_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no action rule matches the category, no_action is returned."""
    # Rule only for category_id=99, but our categorization has category_id=1
    action_rules = [
        ActionRule(category_id=99, action_id=3, conditions=None),
    ]
    monkeypatch.setattr(triage_module, "GenAIHandler", FakeGenAIHandler)
    monkeypatch.setattr(triage_module, "ZammadAPIClient", FakeZammadClient)
    settings = create_mock_settings(action_rules=action_rules)
    triage = Triage(settings=settings)
    categorization = CategorizationResult(category=Category(name="General", id=1), reasoning="ok", confidence=0.8)

    action_id = await triage.get_action_id(categorization_result=categorization, message="msg", session_id="s")
    assert action_id == triage.no_action.id


# ---------------------------------------------------------------------------
# get_action_id: condition priority ordering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_action_id_respects_condition_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    """Higher-priority (lower number) conditions are evaluated first."""
    action_rules = [
        ActionRule(
            category_id=1,
            action_id=1,
            conditions=[
                # priority=2 should be evaluated second
                Condition(priority=2, field="days_since_request", operator="greater_equals", value=1, action_id=99),
                # priority=1 should be evaluated first and match
                Condition(priority=1, field="days_since_request", operator="greater_equals", value=5, action_id=3),
            ],
        ),
    ]
    monkeypatch.setattr(triage_module, "GenAIHandler", FakeGenAIHandler)
    monkeypatch.setattr(triage_module, "ZammadAPIClient", FakeZammadClient)
    settings = create_mock_settings(action_rules=action_rules)
    triage = Triage(settings=settings)
    triage.genai_handler.days_since_request_response = DaysSinceRequestResponse(days_since_request=7, reason="ok")  # type: ignore
    categorization = CategorizationResult(category=Category(name="General", id=1), reasoning="ok", confidence=0.8)

    action_id = await triage.get_action_id(categorization_result=categorization, message="msg", session_id="s")
    # priority=1 condition (>=5, action_id=3) fires first
    assert action_id == 3


# ---------------------------------------------------------------------------
# get_action_id: None category → no_action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_action_id_none_category(patched_triage: Triage) -> None:
    """A None category always returns no_action."""
    categorization = CategorizationResult(category=None, reasoning="no cat", confidence=1.0)
    action_id = await patched_triage.get_action_id(categorization_result=categorization, message="msg", session_id="s")
    assert action_id == patched_triage.no_action.id


# ---------------------------------------------------------------------------
# _id_to_category / _id_to_action helpers
# ---------------------------------------------------------------------------


def test_id_to_category_known(patched_triage: Triage) -> None:
    """Known category ID returns the matching Category."""
    cat = patched_triage._id_to_category(1)
    assert cat.name == "General"


def test_id_to_category_unknown(patched_triage: Triage) -> None:
    """Unknown category ID returns no_category fallback."""
    cat = patched_triage._id_to_category(9999)
    assert cat == patched_triage.no_category


def test_id_to_action_known(patched_triage: Triage) -> None:
    """Known action ID returns the matching Action."""
    action = patched_triage._id_to_action(3)
    assert action.name == "Escalate"


def test_id_to_action_unknown(patched_triage: Triage) -> None:
    """Unknown action ID returns no_action fallback."""
    action = patched_triage._id_to_action(9999)
    assert action == patched_triage.no_action
