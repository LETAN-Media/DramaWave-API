"""Health route (public, no upstream call)."""

from fastapi import APIRouter

from app.config import settings
from app.models import HealthResponse

router = APIRouter()


@router.get('/health', response_model=HealthResponse)
def health() -> HealthResponse:
    # Local-only check: never calls upstream per request.
    return HealthResponse(ok=True, service=settings.app_name, version=settings.version,
                          guest_auth={'configured': True})
