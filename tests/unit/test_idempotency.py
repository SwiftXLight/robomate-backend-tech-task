"""Test idempotency logic."""

from uuid import uuid4

import pytest
from redis.asyncio import Redis

from app.services.redis_service import IdempotencyService


@pytest.mark.asyncio
class TestIdempotency:
    """Test idempotency service."""

    async def test_mark_as_seen_new_event(self, redis_client: Redis):
        """Test marking a new event as seen."""
        service = IdempotencyService(redis_client)
        event_id = uuid4()

        # First time should return True (not duplicate)
        result = await service.mark_as_seen(event_id)
        assert result is True

    async def test_mark_as_seen_duplicate_event(self, redis_client: Redis):
        """Test marking a duplicate event."""
        service = IdempotencyService(redis_client)
        event_id = uuid4()

        # First time
        result1 = await service.mark_as_seen(event_id)
        assert result1 is True

        # Second time should return False (duplicate)
        result2 = await service.mark_as_seen(event_id)
        assert result2 is False

    async def test_is_duplicate_not_seen(self, redis_client: Redis):
        """Test checking if event is duplicate when not seen before."""
        service = IdempotencyService(redis_client)
        event_id = uuid4()

        is_dup = await service.is_duplicate(event_id)
        assert is_dup is False

    async def test_is_duplicate_already_seen(self, redis_client: Redis):
        """Test checking if event is duplicate when already seen."""
        service = IdempotencyService(redis_client)
        event_id = uuid4()

        await service.mark_as_seen(event_id)
        is_dup = await service.is_duplicate(event_id)
        assert is_dup is True

    async def test_check_batch(self, redis_client: Redis):
        """Test batch duplicate checking."""
        service = IdempotencyService(redis_client)

        event_id1 = uuid4()
        event_id2 = uuid4()
        event_id3 = uuid4()

        # Mark event_id2 as seen
        await service.mark_as_seen(event_id2)

        # Check batch
        new_ids, duplicate_ids = await service.check_batch([event_id1, event_id2, event_id3])

        assert event_id1 in new_ids
        assert event_id3 in new_ids
        assert event_id2 in duplicate_ids
        assert len(new_ids) == 2
        assert len(duplicate_ids) == 1

    async def test_mark_batch_as_seen(self, redis_client: Redis):
        """Test marking multiple events as seen."""
        service = IdempotencyService(redis_client)

        event_ids = [uuid4() for _ in range(5)]

        # Mark all as seen
        await service.mark_batch_as_seen(event_ids)

        # Check all are marked
        for event_id in event_ids:
            is_dup = await service.is_duplicate(event_id)
            assert is_dup is True

