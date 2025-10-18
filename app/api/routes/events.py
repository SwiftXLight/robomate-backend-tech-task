"""Event ingestion endpoints."""

import time
from fastapi import APIRouter, Depends, HTTPException, status

from app.models.event import EventBatch, EventResponse, EventCreate
from app.services.event_service import EventService
from app.services.redis_service import IdempotencyService
from app.services.nats_service import NATSPublisher
from app.api.dependencies import (
    get_event_service,
    get_idempotency_service,
    get_nats_publisher,
    check_rate_limit,
)
from app.core import metrics
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/events", tags=["events"])


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(check_rate_limit)],
)
async def ingest_events(
    batch: EventBatch,
    event_service: EventService = Depends(get_event_service),
    idempotency_service: IdempotencyService = Depends(get_idempotency_service),
    nats_publisher: NATSPublisher = Depends(get_nats_publisher),
) -> EventResponse:
    """
    Ingest a batch of events.
    
    - Validates event data
    - Checks for duplicates (idempotency)
    - Publishes to NATS for async processing
    - Returns immediately with acceptance status
    """
    start_time = time.time()
    
    try:
        # Extract event IDs
        event_ids = [event.event_id for event in batch.events]
        
        # Check for duplicates using Redis
        new_ids, duplicate_ids = await idempotency_service.check_batch(event_ids)
        
        # Filter out duplicate events
        new_events = [
            event for event in batch.events 
            if event.event_id in new_ids
        ]
        
        # Track metrics
        for event in batch.events:
            metrics.events_received_total.labels(event_type=event.event_type).inc()
        
        metrics.events_duplicate_total.inc(len(duplicate_ids))
        
        if not new_events:
            logger.info("All events were duplicates", total=len(batch.events))
            return EventResponse(
                accepted=0,
                duplicates=len(duplicate_ids),
                failed=0,
                message="All events were duplicates",
            )
        
        # Mark new events as seen in Redis
        await idempotency_service.mark_batch_as_seen(new_ids)
        
        # Publish to NATS for async processing
        event_dicts = [event.model_dump(mode="json") for event in new_events]
        await nats_publisher.publish_batch(event_dicts)
        
        # Record ingestion time
        duration = time.time() - start_time
        metrics.ingestion_duration_seconds.observe(duration)
        
        logger.info(
            "Events accepted for processing",
            accepted=len(new_events),
            duplicates=len(duplicate_ids),
            duration_seconds=round(duration, 3),
        )
        
        return EventResponse(
            accepted=len(new_events),
            duplicates=len(duplicate_ids),
            failed=0,
            message=f"Accepted {len(new_events)} events for processing",
        )
        
    except Exception as e:
        logger.error("Error ingesting events", error=str(e))
        metrics.events_failed_total.labels(reason="ingestion_error").inc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process events",
        )


@router.get("/count")
async def get_event_count(
    event_service: EventService = Depends(get_event_service),
) -> dict[str, int]:
    """Get total event count in database."""
    # This is a simple utility endpoint
    from sqlalchemy import text
    result = await event_service.session.execute(text("SELECT COUNT(*) FROM events"))
    count = result.scalar()
    return {"total_events": count}

