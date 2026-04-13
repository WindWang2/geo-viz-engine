from datetime import datetime, timezone
from fastapi import APIRouter
from app.models.common import HealthResponse

router = APIRouter(prefix="/api/system", tags=["system"])

APP_VERSION = "0.1.0"


@router.get("/status", response_model=HealthResponse)
async def get_status() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=APP_VERSION,
        timestamp=datetime.now(timezone.utc),
        backend="geo-viz-engine-python",
    )
