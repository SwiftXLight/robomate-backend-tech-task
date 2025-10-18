"""Event service for business logic."""

import json
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.event import EventCreate, DAUResponse, TopEventResponse, RetentionCohort

logger = get_logger(__name__)


class EventService:
    """Service for event-related business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def insert_events(self, events: list[EventCreate]) -> tuple[int, int]:
        """
        Insert events into database.
        
        Returns:
            Tuple of (inserted_count, duplicate_count)
        """
        inserted = 0
        duplicates = 0

        for event in events:
            try:
                # Insert event with ON CONFLICT DO NOTHING for idempotency
                query = text("""
                    INSERT INTO events (event_id, user_id, event_type, occurred_at, properties)
                    VALUES (:event_id, :user_id, :event_type, :occurred_at, :properties)
                    ON CONFLICT (event_id) DO NOTHING
                    RETURNING id
                """)
                
                result = await self.session.execute(
                    query,
                    {
                        "event_id": str(event.event_id),
                        "user_id": event.user_id,
                        "event_type": event.event_type,
                        "occurred_at": event.occurred_at,
                        "properties": json.dumps(event.properties or {}),
                    },
                )
                
                if result.rowcount > 0:
                    inserted += 1
                else:
                    duplicates += 1
                    
            except Exception as e:
                logger.error("Failed to insert event", error=str(e), event_id=event.event_id)
                raise

        await self.session.commit()
        
        logger.info(
            "Events inserted",
            inserted=inserted,
            duplicates=duplicates,
            total=len(events),
        )
        
        return inserted, duplicates

    async def get_dau(self, from_date: str, to_date: str) -> list[DAUResponse]:
        """Get Daily Active Users for date range."""
        # Parse dates
        from_dt = datetime.fromisoformat(from_date).date()
        to_dt = datetime.fromisoformat(to_date).date() + timedelta(days=1)
        
        query = text("""
            SELECT 
                DATE(occurred_at) as date,
                COUNT(DISTINCT user_id) as active_users
            FROM events
            WHERE occurred_at >= :from_date AND occurred_at < :to_date
            GROUP BY DATE(occurred_at)
            ORDER BY date
        """)
        
        result = await self.session.execute(
            query,
            {"from_date": from_dt, "to_date": to_dt},
        )
        
        rows = result.fetchall()
        return [
            DAUResponse(date=str(row.date), active_users=row.active_users)
            for row in rows
        ]

    async def get_top_events(
        self, from_date: str, to_date: str, limit: int = 10
    ) -> list[TopEventResponse]:
        """Get top event types by count."""
        # Parse dates
        from_dt = datetime.fromisoformat(from_date).date()
        to_dt = datetime.fromisoformat(to_date).date() + timedelta(days=1)
        
        query = text("""
            SELECT 
                event_type,
                COUNT(*) as count
            FROM events
            WHERE occurred_at >= :from_date AND occurred_at < :to_date
            GROUP BY event_type
            ORDER BY count DESC
            LIMIT :limit
        """)
        
        result = await self.session.execute(
            query,
            {"from_date": from_dt, "to_date": to_dt, "limit": limit},
        )
        
        rows = result.fetchall()
        return [
            TopEventResponse(event_type=row.event_type, count=row.count)
            for row in rows
        ]

    async def get_retention(
        self, start_date: str, windows: int = 3, window_type: str = "daily"
    ) -> list[RetentionCohort]:
        """
        Calculate cohort retention analysis.
        
        Args:
            start_date: Starting date for cohort analysis
            windows: Number of retention windows to calculate (e.g., 3 means day 0, 1, 2, 3)
            window_type: 'daily' or 'weekly'
        """
        interval = "1 day" if window_type == "daily" else "7 days"
        
        # Get cohort users (users active on start_date)
        start_dt = datetime.fromisoformat(start_date).date()
        cohort_query = text("""
            SELECT DISTINCT user_id
            FROM events
            WHERE DATE(occurred_at) = :start_date
        """)
        
        cohort_result = await self.session.execute(cohort_query, {"start_date": start_dt})
        cohort_users = {row.user_id for row in cohort_result.fetchall()}
        
        if not cohort_users:
            return []
        
        cohort = RetentionCohort(
            cohort_start=start_date,
            window_0=len(cohort_users),
        )
        
        # Calculate retention for each window
        for window in range(1, windows + 1):
            if window_type == "daily":
                window_date = (
                    datetime.fromisoformat(start_date) + timedelta(days=window)
                ).date()
            else:
                window_date = (
                    datetime.fromisoformat(start_date) + timedelta(weeks=window)
                ).date()
            
            # Get users active in this window
            window_query = text("""
                SELECT DISTINCT user_id
                FROM events
                WHERE DATE(occurred_at) = :window_date
                AND user_id = ANY(:cohort_users)
            """)
            
            window_result = await self.session.execute(
                window_query,
                {"window_date": window_date, "cohort_users": list(cohort_users)},
            )
            
            retained_users = len(window_result.fetchall())
            retention_rate = (retained_users / len(cohort_users) * 100) if cohort_users else 0
            
            setattr(cohort, f"window_{window}", retained_users)
            setattr(cohort, f"retention_rate_{window}", round(retention_rate, 2))
        
        return [cohort]

