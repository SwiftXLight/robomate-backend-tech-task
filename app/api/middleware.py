"""Custom middleware for FastAPI."""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core import metrics
from app.core.logging import get_logger

logger = get_logger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect metrics for all requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect metrics."""
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Extract info
        method = request.method
        path = request.url.path
        status_code = response.status_code
        
        # Record metrics
        metrics.api_requests_total.labels(
            method=method,
            endpoint=path,
            status_code=status_code,
        ).inc()
        
        metrics.api_request_duration_seconds.labels(
            method=method,
            endpoint=path,
        ).observe(duration)
        
        # Add rate limit header if available
        if hasattr(request.state, "rate_limit_remaining"):
            response.headers["X-RateLimit-Remaining"] = str(request.state.rate_limit_remaining)
        
        # Log request
        logger.info(
            "Request processed",
            method=method,
            path=path,
            status_code=status_code,
            duration_seconds=round(duration, 3),
        )
        
        return response

