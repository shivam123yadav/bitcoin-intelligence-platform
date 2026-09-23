from fastapi import APIRouter

from app.models.schemas import HealthResponse


router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    from app.config import settings

    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=settings.version,
    )
