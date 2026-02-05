from fastapi import FastAPI

from app.core.settings import Settings, get_settings
from app.kafka.broker import build_router
from app.models.api import TriageInput, TriageReturn
from app.models.triage import CategorizationResult, TriageResult
from app.observe.observer import get_session_id
from app.triage.helper import id_to_action, id_to_category
from app.triage.triage import Triage

settings: Settings = get_settings()
router, _ = build_router(settings=settings)

# Create FastAPI app
backend = FastAPI()

# Include router (this handles broker lifecycle automatically)
backend.include_router(router)


@backend.get("/api/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}


@backend.post("/api/triage")
async def triage(input: TriageInput) -> TriageReturn:
    if not input.id:
        input.id = get_session_id()
    text = input.text

    triage = Triage()

    # Get categorization result
    categorization: CategorizationResult = await triage.predict_category(text, session_id=input.id)

    # Determine action based on category
    action_id = await triage.get_action_id(categorization, text=text, session_id=input.id)
    action = id_to_action(action_id, settings.triage.actions, settings.triage.no_action_id)
    return TriageReturn(
        triage=TriageResult(
            category=categorization.category
            if categorization.category
            else id_to_category(settings.triage.no_category_id, settings.triage.categories, settings.triage.no_category_id),
            action=action,
            reasoning=categorization.reasoning,
            confidence=categorization.confidence,
        ),
        id=input.id,
    )
