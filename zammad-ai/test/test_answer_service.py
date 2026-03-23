from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

import pytest

from app.answer import service as answer_module
from app.answer.service import AnswerService
from app.settings import ZammadAISettings


class FakePromptTemplate:
    def format(self, *, user_text: str, category: str) -> str:
        return f"category={category}; user_text={user_text}"


class FakeLangfuseClient:
    def generate_session_id(self) -> str:
        return "session-id"

    def build_config(self, session_id: str | None = None) -> dict:
        return {"session_id": session_id}


def _get_answer_runs_in_progress_value() -> float:
    for metric in answer_module.ANSWER_RUNS_IN_PROGRESS.collect():
        for sample in metric.samples:
            if sample.name == "zammad_ai_answer_runs_in_progress":
                return sample.value
    raise AssertionError("answer runs in-progress gauge sample not found")


def _build_answer_service(
    ainvoke: Callable[..., Awaitable[dict]],
    settings_factory: Callable[..., ZammadAISettings],
) -> AnswerService:
    service = AnswerService.__new__(AnswerService)
    service.settings = settings_factory(
        overrides={
            "answer": {
                "ai_answer_disclaimer": "",
            },
        }
    )
    service.langfuse_client = FakeLangfuseClient()
    service.user_message_template = FakePromptTemplate()
    service.agent = AsyncMock()
    service.agent.ainvoke = ainvoke
    service.agent_context = object()
    return service


@pytest.mark.asyncio
async def test_generate_answer_in_progress_gauge_returns_to_baseline_on_success(
    settings_factory: Callable[..., ZammadAISettings],
) -> None:
    baseline = _get_answer_runs_in_progress_value()

    async def _ainvoke(*_args, **_kwargs) -> dict:
        return {"structured_response": {"answer": "ok"}}

    service = _build_answer_service(ainvoke=_ainvoke, settings_factory=settings_factory)

    await service.generate_answer(user_text="hello", category="general")

    assert _get_answer_runs_in_progress_value() == baseline


@pytest.mark.asyncio
async def test_generate_answer_in_progress_gauge_increments_while_running(
    settings_factory: Callable[..., ZammadAISettings],
) -> None:
    baseline = _get_answer_runs_in_progress_value()
    expected = baseline + 1

    async def _ainvoke(*_args, **_kwargs) -> dict:
        assert _get_answer_runs_in_progress_value() == expected
        return {"structured_response": {"answer": "ok"}}

    service = _build_answer_service(ainvoke=_ainvoke, settings_factory=settings_factory)

    await service.generate_answer(user_text="hello", category="general")

    assert _get_answer_runs_in_progress_value() == baseline
