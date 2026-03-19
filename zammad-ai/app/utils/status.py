from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from prometheus_client import Enum

STATUS_ENUM = Enum(
    name="zammad_ai_status",
    documentation="Application status. Values: startup, active, ready (idle), shutdown.",
    states=["startup", "active", "ready", "shutdown"],
)

_lifecycle_status = "startup"
_requests_in_flight = 0


def set_status(state: str) -> None:
    global _lifecycle_status
    _lifecycle_status = state
    STATUS_ENUM.state(state)


@asynccontextmanager
async def track_activity() -> AsyncIterator[None]:
    global _requests_in_flight

    _requests_in_flight += 1
    STATUS_ENUM.state("active")
    try:
        yield
    finally:
        _requests_in_flight -= 1
        if _requests_in_flight == 0:
            STATUS_ENUM.state(_lifecycle_status)
        else:
            STATUS_ENUM.state("active")
