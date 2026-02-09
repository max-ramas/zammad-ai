from __future__ import annotations

from typing import Generator

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
from app.models.zammad import ZammadTicket
from app.triage import triage as triage_module
from app.triage.triage import Triage


class FakeLangfuseClient:
    def generate_session_id(self) -> str:
        return "session-id"


class FakeGenAIHandler:
    def __init__(self, genai_settings: GenAISettings, prompts: dict[str, str]) -> None:
        self.prompts = prompts
        self.langfuse_client = FakeLangfuseClient()
        self.categorization_result: CategorizationResult | None = None
        self.days_since_request_response: DaysSinceRequestResponse | None = None
        self.processing_id_response: ProcessingIdResponse | None = None

    async def predict_category(self, input: dict, session_id: str | None = None) -> CategorizationResult:
        if self.categorization_result is None:
            return CategorizationResult(
                category=None,
                reasoning="no result",
                confidence=0.0,
            )
        return self.categorization_result

    async def extract_days_since_request(self, input: dict, session_id: str | None = None) -> DaysSinceRequestResponse:
        if self.days_since_request_response is None:
            return DaysSinceRequestResponse(days_since_request=0, reason="default")
        return self.days_since_request_response

    async def extract_processing_id(self, input: dict, session_id: str | None = None) -> ProcessingIdResponse:
        if self.processing_id_response is None:
            return ProcessingIdResponse(processing_id="", condition_met=False)
        return self.processing_id_response


class FakeZammadClient:
    def __init__(self, settings: ZammadAPISettings) -> None:
        self.settings = settings
        self.ticket: ZammadTicket | None = None

    async def get_ticket(self, id: str) -> ZammadTicket:
        if self.ticket is None:
            return ZammadTicket(id=id, articles=[])
        return self.ticket

    async def post_answer(self, ticket_id: str, text: str, internal: bool = False) -> None:
        raise AssertionError("post_answer should not be called in these tests")

    async def post_shared_draft(self, ticket_id: str, text: str) -> None:
        raise AssertionError("post_shared_draft should not be called in these tests")

    async def add_tag_to_ticket(self, ticket_id: str, tag: str) -> None:
        raise AssertionError("add_tag_to_ticket should not be called in these tests")


def create_mock_settings(action_rules: list[ActionRule] | None = None) -> ZammadAISettings:
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
