from fastapi import APIRouter, Depends, Request

from app.answer import AnswerService
from app.models.answer import StructuredAgentResponse
from app.models.api_v1 import AnswerInput, AnswerOutput


def answer_dependency(request: Request) -> AnswerService:
    """
    Retrieve the request-scoped AnswerService instance stored on the FastAPI application state.

    Parameters:
        request (Request): FastAPI request whose application state contains the AnswerService instance.

    Returns:
        AnswerService: The AnswerService instance found at request.app.state.answer_service.
    """
    return request.app.state.answer_service


answer_router = APIRouter(
    tags=["answer"],
    prefix="/answer",
)


@answer_router.post(path="")
async def answer(
    input: AnswerInput,
    service: AnswerService = Depends(answer_dependency),
) -> AnswerOutput:
    """
    Process an answer request and produce the agent's response based on the provided input.

    Parameters:
        input (AnswerInput): Request payload containing `text` (the user's query), optional `category` (triage category), and optional `id` (session identifier). If `category` is falsy, "Uncategorized" is used.

    Returns:
        AnswerOutput: The agent's response and any supporting documents.
    """
    result: StructuredAgentResponse = await service.generate_answer(
        user_text=input.text,
        category=input.category or "Uncategorized",
        session_id=input.session_id,
    )
    return AnswerOutput(
        response=result.response,
        documents=result.documents,
    )
