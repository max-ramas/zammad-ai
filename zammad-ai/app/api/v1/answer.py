from fastapi import APIRouter, Depends, Request

from app.answer import AnswerService
from app.models.answer import StructuredAgentResponse
from app.models.api_v1 import AnswerInput, AnswerOutput


def answer_dependency(request: Request) -> AnswerService:
    """
    Retrieve the request-scoped AnswerService instance stored on the FastAPI application state.

    Parameters:
        request (Request): FastAPI request whose application state contains the Triage instance.

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
    Handle an answer request by invoking the answer agent with the provided question and category.

    Parameters:
        input (AnswerInput): Request payload containing `question` (the user's question) and `category` (the triage category).

    Returns:
        AnswerOutput: Contains the agent's structured response to the question.
    """
    result: StructuredAgentResponse = await service.generate_answer(
        user_text=input.text,
        category=input.category or "Uncategorized",
        session_id=input.id,
    )
    return AnswerOutput(
        response=result.response,
        documents=result.documents,
    )
