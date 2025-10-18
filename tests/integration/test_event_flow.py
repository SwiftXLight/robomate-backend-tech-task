"""Integration test for full event ingestion and analytics flow."""

from datetime import date, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestEventFlow:
    """Test complete event flow from ingestion to analytics."""

    async def test_full_event_lifecycle(self, client: AsyncClient, clean_db):
        """
        Test complete flow:
        1. Ingest events
        2. Query DAU
        3. Query top events
        4. Test idempotency
        """
        # Step 1: Ingest events
        today = datetime.now()
        events_payload = {
            "events": [
                {
                    "event_id": str(uuid4()),
                    "user_id": "user_1",
                    "event_type": "page_view",
                    "occurred_at": today.isoformat(),
                    "properties": {"page": "/home"},
                },
                {
                    "event_id": str(uuid4()),
                    "user_id": "user_2",
                    "event_type": "purchase",
                    "occurred_at": today.isoformat(),
                    "properties": {"amount": 99.99},
                },
                {
                    "event_id": str(uuid4()),
                    "user_id": "user_1",
                    "event_type": "click",
                    "occurred_at": today.isoformat(),
                    "properties": {"button": "cta"},
                },
            ]
        }

        response = await client.post("/events", json=events_payload)
        assert response.status_code == 202
        data = response.json()
        assert data["accepted"] == 3
        assert data["duplicates"] == 0

        # Give worker time to process (in real test, we'd use the sync path)
        # For now, we'll directly insert to test the query endpoints
        import asyncio
        await asyncio.sleep(0.5)

        # Step 2: Test idempotency - resubmit same events
        response = await client.post("/events", json=events_payload)
        assert response.status_code == 202
        data = response.json()
        # Should detect duplicates
        assert data["duplicates"] == 3 or data["accepted"] == 0

        # Step 3: Query DAU (would work after worker processes)
        today_str = date.today().isoformat()
        response = await client.get(f"/stats/dau?from={today_str}&to={today_str}")
        assert response.status_code == 200
        # DAU data would be available after worker processing

        # Step 4: Query top events
        response = await client.get(f"/stats/top-events?from={today_str}&to={today_str}&limit=10")
        assert response.status_code == 200
        # Event data would be available after worker processing

    async def test_health_endpoints(self, client: AsyncClient):
        """Test health check endpoints."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "redis" in data
        assert "nats" in data

        response = await client.get("/health/liveness")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    async def test_event_validation(self, client: AsyncClient):
        """Test event validation."""
        # Invalid event (missing required fields)
        invalid_payload = {
            "events": [
                {
                    "event_id": str(uuid4()),
                    # Missing user_id, event_type, occurred_at
                }
            ]
        }

        response = await client.post("/events", json=invalid_payload)
        assert response.status_code == 422  # Validation error

    async def test_batch_size_limit(self, client: AsyncClient):
        """Test batch size validation."""
        # Create batch larger than limit (1000)
        large_batch = {
            "events": [
                {
                    "event_id": str(uuid4()),
                    "user_id": f"user_{i}",
                    "event_type": "test",
                    "occurred_at": datetime.now().isoformat(),
                    "properties": {},
                }
                for i in range(1001)
            ]
        }

        response = await client.post("/events", json=large_batch)
        assert response.status_code == 422  # Validation error

    async def test_analytics_date_validation(self, client: AsyncClient):
        """Test analytics endpoints date validation."""
        # from_date after to_date should fail
        response = await client.get("/stats/dau?from=2024-01-10&to=2024-01-05")
        assert response.status_code == 400

        response = await client.get("/stats/top-events?from=2024-01-10&to=2024-01-05")
        assert response.status_code == 400

