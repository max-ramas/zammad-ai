from logging import Logger

from app.answer.service import AnswerService
from app.models.answer import StructuredAgentResponse
from app.models.triage import Action
from app.settings.settings import ZammadAISettings
from app.settings.triage import ActionTypes
from app.settings.zammad import ZammadAPISettings, ZammadEAISettings
from app.triage.triage import TriageResult
from app.utils.logging import getLogger
from app.zammad.api import ZammadAPIClient
from app.zammad.eai import ZammadEAIClient


class ActionService:
    """
    Service class that gets the Category and Action from Triage and either returns a ai response, standard answer or does nothing based on the ActionType.
    """

    logger: Logger = getLogger("zammad-ai.action.service")

    def __init__(self, settings: ZammadAISettings, answer_service: AnswerService):
        self.settings: ZammadAISettings = settings
        self.answer_service: AnswerService = answer_service
        # Zammad client setup
        if isinstance(self.settings.zammad, ZammadAPISettings):
            self.zammad_client = ZammadAPIClient(settings=self.settings.zammad)
        elif isinstance(self.settings.zammad, ZammadEAISettings):
            self.zammad_client = ZammadEAIClient(settings=self.settings.zammad)
        else:
            raise ValueError("Invalid type for Zammad settings in configuration")

    async def execute_action(self, ticket_id: int, triage: TriageResult) -> None:
        category_name: str = triage.category.name
        action: Action = triage.action

        if action.type == ActionTypes.No_Action:
            self.logger.info(f"No action taken for ticket {ticket_id} with category {category_name}")
            return
        elif action.type == ActionTypes.AI_Answer:
            response: StructuredAgentResponse = await self.answer_service.generate_answer(
                user_text=triage.user_text, category=category_name
            )
            answer: str = response.response
        elif action.type == ActionTypes.Standard_Answer:
            if not action.answer:
                self.logger.warning(
                    f"Action {action.name} is of type Standard_Answer but has no answer defined. No answer will be posted for ticket {ticket_id}."
                )
                return
            answer: str = action.answer
        else:
            raise ValueError(f"Unknown action type: {action.type}")

        if triage.category.auto_publish:
            await self.zammad_client.post_answer(
                ticket_id=ticket_id,
                text=answer,
                subject=None,  # TODO
                internal=False,
            )
            self.logger.info(f"Posted answer for ticket {ticket_id} with category {category_name}")
        else:
            await self.zammad_client.post_shared_draft(
                ticket_id=ticket_id,
                text=answer,
            )
            self.logger.info(f"Posted shared draft for ticket {ticket_id} with category {category_name}")
