import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from logging import Logger
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Counter, Histogram, generate_latest
from starlette.responses import Response

from app.answer import get_answer_service
from app.frontend import mount_frontend
from app.kafka.broker import build_router
from app.models.api_v1 import HealthCheckResponse
from app.settings import ZammadAISettings, get_settings
from app.triage import get_triage_service
from app.utils.logging import getLogger
from app.utils.status import set_status, track_activity

from .v1.answer import answer_router
from .v1.triage import triage_router

logger: Logger = getLogger("zammad-ai.api.backend")

HTTP_REQUESTS_TOTAL = Counter(
    name="zammad_ai_http_requests_total",
    documentation="Total HTTP requests processed by FastAPI.",
    labelnames=("method", "path", "status"),
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    name="zammad_ai_http_request_duration_seconds",
    documentation="HTTP request processing duration in seconds.",
    labelnames=("method", "path", "status"),
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application startup and shutdown by initializing and cleaning shared services.

    On startup, attaches `triage_service` and `answer_service` to `app.state` using current settings. On shutdown, awaits each service's `cleanup()` method; `asyncio.CancelledError` raised during cleanup is caught.
    """
    # Startup: Initialize shared Triage instance
    set_status("startup")
    settings: ZammadAISettings = get_settings()

    logger.info("Initializing shared Triage instance")
    app.state.triage_service = get_triage_service(settings=settings)
    app.state.answer_service = get_answer_service(settings=settings)
    set_status("ready")

    yield
    logger.info("Shutting down shared Triage instance")
    set_status("shutdown")
    try:
        await app.state.triage_service.cleanup()
        await app.state.answer_service.cleanup()

    except asyncio.CancelledError:
        logger.info("Cleanup cancelled during shutdown.")


settings: ZammadAISettings = get_settings()
kafka_router, _ = build_router(settings=settings)

# Create FastAPI app with lifespan
backend = FastAPI(
    lifespan=lifespan,
    title="Zammad AI Backend",
    description="Backend service for Zammad AI, handling Kafka events and REST API for ticket triage and answer generation.",
    docs_url="/api/docs" if settings.mode == "development" else None,
    redoc_url="/api/redoc" if settings.mode == "development" else None,
)


@backend.middleware("http")
async def prometheus_http_metrics_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    start_time: float = perf_counter()
    method: str = request.method
    status_code = 500
    try:
        if request.url.path in ("/triage", "/answer"):
            async with track_activity():
                response: Response = await call_next(request)
                status_code = response.status_code
        else:
            response = await call_next(request)
            status_code = response.status_code
    except Exception:
        raise
    finally:
        route = request.scope.get("route")
        route_path: str = route.path if route is not None and hasattr(route, "path") else "unmatched"
        HTTP_REQUESTS_TOTAL.labels(method=method, path=route_path, status=str(status_code)).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=route_path, status=str(status_code)).observe(perf_counter() - start_time)

    return response


@backend.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


# Include Kafka router (this handles broker lifecycle automatically)
backend.include_router(
    router=kafka_router,
)

# Mount API routers
backend.include_router(
    router=triage_router,
    prefix="/api/v1",
)

backend.include_router(
    router=answer_router,
    prefix="/api/v1",
)

if settings.frontend.enabled:
    backend = mount_frontend(app=backend, frontend_settings=settings.frontend)

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
