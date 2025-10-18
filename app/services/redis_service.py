"""Redis service for idempotency and rate limiting."""

import redis.asyncio as aioredis
from uuid import UUID

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global Redis client
_redis_client: aioredis.Redis | None = None


async def get_redis_client() -> aioredis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info("Redis client created", url=settings.redis_url)
    return _redis_client


async def close_redis_client() -> None:
    """Close Redis client."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        logger.info("Redis client closed")
        _redis_client = None


class IdempotencyService:
    """Service for handling event idempotency using Redis."""

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.ttl = settings.redis_idempotency_ttl

    def _get_key(self, event_id: UUID) -> str:
        """Generate Redis key for event_id."""
        return f"event:seen:{event_id}"

    async def is_duplicate(self, event_id: UUID) -> bool:
        """Check if event_id has been seen before."""
        key = self._get_key(event_id)
        return await self.redis.exists(key) > 0

    async def mark_as_seen(self, event_id: UUID) -> bool:
        """
        Mark event_id as seen.
        
        Returns:
            True if successfully marked (was not seen before)
            False if already existed (duplicate)
        """
        key = self._get_key(event_id)
        # SET NX: Set if not exists
        result = await self.redis.set(key, "1", ex=self.ttl, nx=True)
        return result is not None

    async def check_batch(self, event_ids: list[UUID]) -> tuple[list[UUID], list[UUID]]:
        """
        Check a batch of event_ids for duplicates.
        
        Returns:
            Tuple of (new_event_ids, duplicate_event_ids)
        """
        new_ids = []
        duplicate_ids = []

        # Use pipeline for efficiency
        pipe = self.redis.pipeline()
        for event_id in event_ids:
            pipe.exists(self._get_key(event_id))
        
        results = await pipe.execute()

        for event_id, exists in zip(event_ids, results):
            if exists:
                duplicate_ids.append(event_id)
            else:
                new_ids.append(event_id)

        return new_ids, duplicate_ids

    async def mark_batch_as_seen(self, event_ids: list[UUID]) -> None:
        """Mark multiple event_ids as seen."""
        pipe = self.redis.pipeline()
        for event_id in event_ids:
            key = self._get_key(event_id)
            pipe.set(key, "1", ex=self.ttl, nx=True)
        await pipe.execute()


class RateLimiter:
    """Token bucket rate limiter using Redis."""

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.max_requests = settings.rate_limit_requests
        self.window = settings.rate_limit_window

    def _get_key(self, client_id: str) -> str:
        """Generate Redis key for rate limiting."""
        return f"rate_limit:{client_id}"

    async def is_allowed(self, client_id: str) -> tuple[bool, int]:
        """
        Check if request is allowed for client.
        
        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        if not settings.rate_limit_enabled:
            return True, self.max_requests

        key = self._get_key(client_id)
        
        # Increment counter
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, self.window)
        results = await pipe.execute()
        
        current_count = results[0]
        remaining = max(0, self.max_requests - current_count)
        
        return current_count <= self.max_requests, remaining

    async def get_remaining(self, client_id: str) -> int:
        """Get remaining requests for client."""
        key = self._get_key(client_id)
        count = await self.redis.get(key)
        if count is None:
            return self.max_requests
        return max(0, self.max_requests - int(count))

