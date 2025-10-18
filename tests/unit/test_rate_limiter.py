"""Test rate limiting logic."""

import pytest
from redis.asyncio import Redis

from app.services.redis_service import RateLimiter
from app.core.config import settings


@pytest.mark.asyncio
class TestRateLimiter:
    """Test rate limiting service."""

    async def test_first_request_allowed(self, redis_client: Redis):
        """Test that first request is always allowed."""
        limiter = RateLimiter(redis_client)
        client_id = "test_client_1"

        is_allowed, remaining = await limiter.is_allowed(client_id)
        assert is_allowed is True
        assert remaining == settings.rate_limit_requests - 1

    async def test_rate_limit_enforced(self, redis_client: Redis):
        """Test that rate limit is enforced."""
        limiter = RateLimiter(redis_client)
        limiter.max_requests = 5  # Set low limit for testing
        client_id = "test_client_2"

        # Make 5 allowed requests
        for i in range(5):
            is_allowed, remaining = await limiter.is_allowed(client_id)
            assert is_allowed is True
            assert remaining == 4 - i

        # 6th request should be blocked
        is_allowed, remaining = await limiter.is_allowed(client_id)
        assert is_allowed is False
        assert remaining == 0

    async def test_different_clients_independent(self, redis_client: Redis):
        """Test that different clients have independent limits."""
        limiter = RateLimiter(redis_client)
        limiter.max_requests = 3

        client1 = "test_client_3"
        client2 = "test_client_4"

        # Exhaust client1's limit
        for _ in range(3):
            await limiter.is_allowed(client1)

        # client1 should be blocked
        is_allowed1, _ = await limiter.is_allowed(client1)
        assert is_allowed1 is False

        # client2 should still be allowed
        is_allowed2, _ = await limiter.is_allowed(client2)
        assert is_allowed2 is True

    async def test_get_remaining(self, redis_client: Redis):
        """Test getting remaining requests."""
        limiter = RateLimiter(redis_client)
        limiter.max_requests = 10
        client_id = "test_client_5"

        # Initial remaining
        remaining = await limiter.get_remaining(client_id)
        assert remaining == 10

        # After 3 requests
        for _ in range(3):
            await limiter.is_allowed(client_id)

        remaining = await limiter.get_remaining(client_id)
        assert remaining == 7

