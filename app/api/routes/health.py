"""Health check endpoints."""

from fastapi import APIRouter, status
from pydantic import BaseModel

from app.db.database import check_db_connection
from app.services.redis_service import get_redis_client
from app.services.nats_service import get_nats_client

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str
    database: str
    redis: str
    nats: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check health of all services."""
    db_ok = await check_db_connection()
    
    try:
        redis_client = await get_redis_client()
        await redis_client.ping()
        redis_ok = "healthy"
    except Exception:
        redis_ok = "unhealthy"
    
    try:
        nats_client = await get_nats_client()
        nats_ok = "healthy" if nats_client.is_connected else "unhealthy"
    except Exception:
        nats_ok = "unhealthy"
    
    overall_status = (
        "healthy" if all([db_ok, redis_ok == "healthy", nats_ok == "healthy"])
        else "unhealthy"
    )
    
    return HealthResponse(
        status=overall_status,
        database="healthy" if db_ok else "unhealthy",
        redis=redis_ok,
        nats=nats_ok,
    )


@router.get("/health/liveness")
async def liveness() -> dict[str, str]:
    """Liveness probe for Kubernetes."""
    return {"status": "alive"}


@router.get("/health/readiness")
async def readiness() -> dict[str, str]:
    """Readiness probe for Kubernetes."""
    db_ok = await check_db_connection()
    
    if not db_ok:
        return {"status": "not ready"}
    
    return {"status": "ready"}

