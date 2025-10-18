"""NATS worker for processing events from the queue."""

import asyncio
import json
import signal
import sys
from typing import Any

from nats.aio.msg import Msg
from nats.js.api import ConsumerConfig, AckPolicy

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core import metrics
from app.db.database import get_db_session
from app.services.event_service import EventService
from app.services.nats_service import get_nats_client, get_jetstream
from app.models.event import EventCreate

# Configure logging
configure_logging()
logger = get_logger(__name__)

# Global shutdown flag
shutdown_flag = False


def signal_handler(signum: int, frame: Any) -> None:
    """Handle shutdown signals."""
    global shutdown_flag
    logger.info("Received shutdown signal", signal=signum)
    shutdown_flag = True


async def process_event(msg: Msg) -> None:
    """
    Process a single event message from NATS.
    
    Args:
        msg: NATS message containing event data
    """
    try:
        # Parse message
        event_data = json.loads(msg.data.decode())
        logger.debug("Processing event", event_id=event_data.get("event_id"))
        
        # Convert to Pydantic model
        event = EventCreate(**event_data)
        
        # Store in database
        async with get_db_session() as session:
            event_service = EventService(session)
            inserted, duplicates = await event_service.insert_events([event])
        
        # Track metrics
        if inserted > 0:
            metrics.events_ingested_total.labels(event_type=event.event_type).inc()
            logger.debug("Event stored successfully", event_id=event.event_id)
        else:
            logger.debug("Event was duplicate", event_id=event.event_id)
        
        # Acknowledge message
        await msg.ack()
        
    except json.JSONDecodeError as e:
        logger.error("Failed to decode message", error=str(e))
        await msg.term()  # Terminate message (won't be retried)
        metrics.events_failed_total.labels(reason="decode_error").inc()
        
    except Exception as e:
        logger.error("Failed to process event", error=str(e))
        # NAK the message so it will be retried
        await msg.nak(delay=5)  # Retry after 5 seconds
        metrics.events_failed_total.labels(reason="processing_error").inc()


async def run_worker() -> None:
    """Run the event processing worker."""
    logger.info("Starting event processor worker")
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Connect to NATS
        nats_client = await get_nats_client()
        js = await get_jetstream()
        
        # Create or get consumer
        consumer_config = ConsumerConfig(
            durable_name=settings.nats_consumer_name,
            ack_policy=AckPolicy.EXPLICIT,
            max_deliver=3,  # Max retry attempts
            ack_wait=30,  # Wait 30s for ack before redelivery
        )
        
        # Subscribe to stream
        subscription = await js.pull_subscribe(
            subject=settings.nats_subject,
            durable=settings.nats_consumer_name,
            config=consumer_config,
        )
        
        logger.info(
            "Worker subscribed to NATS",
            stream=settings.nats_stream_name,
            subject=settings.nats_subject,
            consumer=settings.nats_consumer_name,
        )
        
        # Process messages
        while not shutdown_flag:
            try:
                # Fetch batch of messages
                messages = await subscription.fetch(batch=10, timeout=1.0)
                
                for msg in messages:
                    if shutdown_flag:
                        break
                    await process_event(msg)
                    
            except TimeoutError:
                # No messages available, continue polling
                continue
            except Exception as e:
                logger.error("Error in worker loop", error=str(e))
                await asyncio.sleep(1)
        
        logger.info("Worker shutting down gracefully")
        
    except Exception as e:
        logger.error("Worker failed to start", error=str(e))
        sys.exit(1)


def main() -> None:
    """Main entry point for the worker."""
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error("Worker crashed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()

