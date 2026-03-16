"""
Answer module for Zammad AI, responsible for generating structured responses to user questions using an agent-based approach.
"""

from .agent import AgentContext, StructuredAgentResponse
from .service import AnswerService, get_answer_service

__all__: list[str] = [
    "AgentContext",
    "AnswerService",
    "get_answer_service",
    "StructuredAgentResponse",
]
