"""Event data models using Pydantic."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class EventBase(BaseModel):
    """Base event model with common fields."""

    event_id: UUID = Field(..., description="Unique event identifier for idempotency")
    user_id: str = Field(..., min_length=1, max_length=255, description="User identifier")
    event_type: str = Field(..., min_length=1, max_length=100, description="Type of event")
    occurred_at: datetime = Field(..., description="When the event occurred (ISO-8601)")
    properties: dict[str, Any] = Field(default_factory=dict, description="Event properties")

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, v: datetime) -> datetime:
        """Ensure occurred_at is not in the future."""
        if v > datetime.now(v.tzinfo):
            raise ValueError("occurred_at cannot be in the future")
        return v


class EventCreate(EventBase):
    """Event creation model (input from API)."""

    pass


class EventInDB(EventBase):
    """Event as stored in database."""

    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class EventBatch(BaseModel):
    """Batch of events for ingestion."""

    events: list[EventCreate] = Field(..., min_length=1, description="List of events to ingest")

    @field_validator("events")
    @classmethod
    def validate_batch_size(cls, v: list[EventCreate]) -> list[EventCreate]:
        """Limit batch size."""
        if len(v) > 1000:
            raise ValueError("Batch size cannot exceed 1000 events")
        return v


class EventResponse(BaseModel):
    """Response after event ingestion."""

    accepted: int = Field(..., description="Number of events accepted")
    duplicates: int = Field(default=0, description="Number of duplicate events skipped")
    failed: int = Field(default=0, description="Number of failed events")
    message: str = Field(default="Events processed successfully")


# Analytics models

class DAUResponse(BaseModel):
    """Daily Active Users response."""

    date: str
    active_users: int


class TopEventResponse(BaseModel):
    """Top events response."""

    event_type: str
    count: int


class RetentionCohort(BaseModel):
    """Retention cohort data."""

    cohort_start: str
    window_0: int  # Users in cohort
    window_1: int | None = None  # Retained users in window 1
    window_2: int | None = None  # Retained users in window 2
    window_3: int | None = None  # Retained users in window 3
    retention_rate_1: float | None = None
    retention_rate_2: float | None = None
    retention_rate_3: float | None = None


class RetentionResponse(BaseModel):
    """Retention analysis response."""

    cohorts: list[RetentionCohort]
    window_type: str = Field(default="daily", description="Type of window (daily or weekly)")

