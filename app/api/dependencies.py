"""FastAPI dependencies."""

from collections.abc import AsyncGenerator
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.services.redis_service import (
    get_redis_client,
    IdempotencyService,
    RateLimiter,
)
from app.services.nats_service import get_jetstream, NATSPublisher
from app.services.event_service import EventService
from app.core import metrics
from app.core.logging import get_logger

logger = get_logger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async for session in get_session():
        yield session


async def get_event_service(
    session: AsyncSession = Depends(get_db),
) -> EventService:
    """Get event service instance."""
    return EventService(session)


async def get_idempotency_service() -> IdempotencyService:
    """Get idempotency service instance."""
    redis_client = await get_redis_client()
    return IdempotencyService(redis_client)


async def get_rate_limiter() -> RateLimiter:
    """Get rate limiter instance."""
    redis_client = await get_redis_client()
    return RateLimiter(redis_client)


async def get_nats_publisher() -> NATSPublisher:
    """Get NATS publisher instance."""
    js = await get_jetstream()
    return NATSPublisher(js)


async def check_rate_limit(
    request: Request,
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> None:
    """Middleware to check rate limiting."""
    client_ip = request.client.host if request.client else "unknown"
    
    is_allowed, remaining = await rate_limiter.is_allowed(client_ip)
    
    # Add rate limit headers
    request.state.rate_limit_remaining = remaining
    
    if not is_allowed:
        metrics.rate_limit_exceeded_total.labels(client_ip=client_ip).inc()
        logger.warning("Rate limit exceeded", client_ip=client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
            headers={"X-RateLimit-Remaining": "0"},
        )

