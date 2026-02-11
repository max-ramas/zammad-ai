from fastapi import APIRouter

from app.answer.agent import StructuredAgentResponse
from app.answer.answer import formulate_answer
from app.models.api_v1 import AnswerInput, AnswerOutput

answer_router = APIRouter(
    tags=["answer"],
    prefix="/answer",
)


@answer_router.post(path="")
async def answer(
    input: AnswerInput,
) -> AnswerOutput:
    """
    Handle an answer request by invoking the answer agent with the provided question and category.

    Parameters:
        input (AnswerInput): Request payload containing `question` (the user's question) and `category` (the triage category).

    Returns:
        AnswerOutput: Contains the agent's structured response to the question.
    """
    result: StructuredAgentResponse = await formulate_answer(
        question=input.text,
        category=str(input.category),
        session_id=input.id,
    )
    return AnswerOutput(
        response=result.response,
        documents=result.documents,
    )
