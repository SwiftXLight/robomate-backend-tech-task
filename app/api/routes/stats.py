"""Analytics and statistics endpoints."""

from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException

from app.models.event import DAUResponse, TopEventResponse, RetentionResponse
from app.services.event_service import EventService
from app.api.dependencies import get_event_service
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/stats", tags=["statistics"])


@router.get("/dau", response_model=list[DAUResponse])
async def get_daily_active_users(
    from_date: date = Query(..., alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: date = Query(..., alias="to", description="End date (YYYY-MM-DD)"),
    event_service: EventService = Depends(get_event_service),
) -> list[DAUResponse]:
    """
    Get Daily Active Users (DAU) for a date range.
    
    Returns the count of unique user_ids per day.
    """
    if from_date > to_date:
        raise HTTPException(status_code=400, detail="from_date must be before to_date")
    
    logger.info("Fetching DAU", from_date=str(from_date), to_date=str(to_date))
    
    result = await event_service.get_dau(str(from_date), str(to_date))
    
    logger.info("DAU fetched", count=len(result))
    return result


@router.get("/top-events", response_model=list[TopEventResponse])
async def get_top_events(
    from_date: date = Query(..., alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: date = Query(..., alias="to", description="End date (YYYY-MM-DD)"),
    limit: int = Query(10, ge=1, le=100, description="Number of top events to return"),
    event_service: EventService = Depends(get_event_service),
) -> list[TopEventResponse]:
    """
    Get top event types by count for a date range.
    
    Returns the most frequent event types.
    """
    if from_date > to_date:
        raise HTTPException(status_code=400, detail="from_date must be before to_date")
    
    logger.info(
        "Fetching top events",
        from_date=str(from_date),
        to_date=str(to_date),
        limit=limit,
    )
    
    result = await event_service.get_top_events(str(from_date), str(to_date), limit)
    
    logger.info("Top events fetched", count=len(result))
    return result


@router.get("/retention", response_model=RetentionResponse)
async def get_retention(
    start_date: date = Query(..., description="Cohort start date (YYYY-MM-DD)"),
    windows: int = Query(3, ge=1, le=10, description="Number of retention windows"),
    window_type: str = Query("daily", regex="^(daily|weekly)$", description="Window type"),
    event_service: EventService = Depends(get_event_service),
) -> RetentionResponse:
    """
    Get cohort retention analysis.
    
    - Cohort: Users who were active on start_date
    - Windows: How many periods to track (e.g., 3 = day 0, 1, 2, 3)
    - Window type: 'daily' or 'weekly'
    
    Returns retention rates showing what percentage of the cohort
    remained active in subsequent windows.
    """
    logger.info(
        "Fetching retention",
        start_date=str(start_date),
        windows=windows,
        window_type=window_type,
    )
    
    cohorts = await event_service.get_retention(
        str(start_date),
        windows=windows,
        window_type=window_type,
    )
    
    logger.info("Retention fetched", cohorts=len(cohorts))
    
    return RetentionResponse(cohorts=cohorts, window_type=window_type)

