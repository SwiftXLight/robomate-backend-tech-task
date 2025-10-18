"""NATS JetStream service for async event processing."""

import json
from typing import Any

from nats.aio.client import Client as NATS
from nats.js import JetStreamContext
from nats.js.api import StreamConfig, RetentionPolicy, StorageType

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global NATS client
_nats_client: NATS | None = None
_jetstream: JetStreamContext | None = None


async def get_nats_client() -> NATS:
    """Get or create NATS client."""
    global _nats_client, _jetstream
    
    if _nats_client is None:
        _nats_client = NATS()
        await _nats_client.connect(settings.nats_url)
        _jetstream = _nats_client.jetstream()
        
        # Create or update stream
        try:
            await _jetstream.add_stream(
                StreamConfig(
                    name=settings.nats_stream_name,
                    subjects=[settings.nats_subject],
                    retention=RetentionPolicy.WORK_QUEUE,
                    storage=StorageType.FILE,
                    max_age=86400 * 7,  # 7 days
                    max_msgs=1_000_000,
                    max_bytes=1024 * 1024 * 1024,  # 1GB
                )
            )
            logger.info(
                "NATS stream created/updated",
                stream=settings.nats_stream_name,
                subject=settings.nats_subject,
            )
        except Exception as e:
            logger.warning("Stream might already exist", error=str(e))
        
        logger.info("NATS client connected", url=settings.nats_url)
    
    return _nats_client


async def get_jetstream() -> JetStreamContext:
    """Get JetStream context."""
    global _jetstream
    if _jetstream is None:
        await get_nats_client()
    return _jetstream


async def close_nats_client() -> None:
    """Close NATS client."""
    global _nats_client, _jetstream
    if _nats_client:
        await _nats_client.close()
        logger.info("NATS client closed")
        _nats_client = None
        _jetstream = None


class NATSPublisher:
    """Publisher for sending events to NATS JetStream."""

    def __init__(self, jetstream: JetStreamContext):
        self.js = jetstream

    async def publish_event(self, event_data: dict[str, Any]) -> None:
        """Publish single event to NATS."""
        subject = settings.nats_subject
        payload = json.dumps(event_data).encode()
        
        try:
            ack = await self.js.publish(subject, payload)
            logger.debug(
                "Event published to NATS",
                subject=subject,
                stream=ack.stream,
                sequence=ack.seq,
            )
        except Exception as e:
            logger.error("Failed to publish event to NATS", error=str(e), event_id=event_data.get("event_id"))
            raise

    async def publish_batch(self, events: list[dict[str, Any]]) -> None:
        """Publish batch of events to NATS."""
        for event in events:
            await self.publish_event(event)
        
        logger.info("Batch published to NATS", count=len(events))

