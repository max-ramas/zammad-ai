from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from logging import Logger

from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse

from app.core.settings import ZammadAISettings, get_settings
from app.kafka.broker import build_router
from app.models.api_v1 import HealthCheckReponse
from app.triage import Triage
from app.utils.logging import getLogger

from .v1.triage import get_triage, triage_router

logger: Logger = getLogger("zammad-ai.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage FastAPI application lifespan.

    This context manager initializes shared resources on startup
    and cleans them up on shutdown.

    Args:
        app: The FastAPI application instance
    """
    # Startup: Initialize shared context
    settings: ZammadAISettings = get_settings()

    logger.info("Initializing backend context with shared Triage instance")
    app.state.triage = Triage(settings=settings)

    yield

    # Shutdown: Cleanup resources
    logger.info("Shutting down backend context")
    await app.state.backend_context.cleanup()


settings: ZammadAISettings = get_settings()
router, _ = build_router(settings=settings)

# Create FastAPI app with lifespan
backend = FastAPI(
    lifespan=lifespan,
    title="Zammad AI Backend",
    description="Backend service for Zammad AI, handling Kafka events and REST API for ticket triage and answer generation.",
    docs_url="/api/docs" if settings.mode == "development" else None,
    redoc_url="/api/redoc" if settings.mode == "development" else None,
)

# Include Kafka router (this handles broker lifecycle automatically)
backend.include_router(router=router)

# Mount API routers
backend.include_router(
    router=triage_router,
    prefix="/api/v1/triage",
    tags=["triage"],
    dependencies=[Depends(get_triage)],
)

if not settings.frontend.enabled:
    logger.info("Frontend is disabled, rerouting root path to API docs")

    @backend.get("/", include_in_schema=False)
    async def reroute_to_docs() -> RedirectResponse:
        return RedirectResponse(url="/api/docs")


@backend.get("/api/v1/health", tags=["health"])
async def health_check() -> HealthCheckReponse:
    return HealthCheckReponse()
