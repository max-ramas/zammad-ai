from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from logging import Logger

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.core.settings import ZammadAISettings, get_settings
from app.kafka.broker import build_router
from app.models.api_v1 import HealthCheckResponse
from app.triage.triage import get_triage
from app.utils.logging import getLogger

from .v1.answer import answer_router
from .v1.triage import triage_router

logger: Logger = getLogger("zammad-ai.api.backend")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage the application lifespan by initializing shared resources on startup and releasing them on shutdown.

    On startup, initializes the Triage instance. On shutdown, performs cleanup.

    Parameters:
        app (FastAPI): The FastAPI application.
    """
    # Startup: Initialize shared Triage instance
    settings: ZammadAISettings = get_settings()

    logger.info("Initializing shared Triage instance")
    app.state.triage = get_triage(settings=settings)

    yield

    # Shutdown: Cleanup resources
    logger.info("Shutting down shared Triage instance")
    await app.state.triage.cleanup()


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
    prefix="/api/v1",
)

backend.include_router(
    router=answer_router,
    prefix="/api/v1",
)

if not settings.frontend.enabled and settings.mode == "development":
    logger.info("Frontend is disabled, rerouting root path to API docs")

    @backend.get("/", include_in_schema=False)
    async def reroute_to_docs() -> RedirectResponse:
        """
        Redirect root requests to the API documentation page.

        Returns:
            RedirectResponse: A response that redirects the client to "/api/docs".
        """
        return RedirectResponse(url="/api/docs")


@backend.get("/api/v1/health", tags=["health"])
async def health_check() -> HealthCheckResponse:
    """
    Provide a basic application health check response.

    Returns:
        HealthCheckResponse: An instance containing the application's default health status.
    """
    return HealthCheckResponse()
