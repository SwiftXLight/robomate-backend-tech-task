"""FastAPI main application."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.database import check_db_connection, close_db_connection
from app.services.redis_service import get_redis_client, close_redis_client
from app.services.nats_service import get_nats_client, close_nats_client
from app.api.middleware import MetricsMiddleware
from app.api.routes import events, stats, health

# Configure logging
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler."""
    # Startup
    logger.info("Starting application", version=app.version)
    
    # Initialize connections
    try:
        # Database
        db_ok = await check_db_connection()
        if not db_ok:
            logger.error("Database connection failed!")
        else:
            logger.info("Database connection established")
        
        # Redis
        redis_client = await get_redis_client()
        await redis_client.ping()
        logger.info("Redis connection established")
        
        # NATS
        nats_client = await get_nats_client()
        logger.info("NATS connection established")
        
    except Exception as e:
        logger.error("Failed to initialize connections", error=str(e))
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    await close_db_connection()
    await close_redis_client()
    await close_nats_client()
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Event ingestion and analytics service with NATS JetStream",
    version="0.1.0",
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(MetricsMiddleware)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(events.router)
app.include_router(stats.router)

# Mount Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "service": settings.app_name,
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "metrics": "/metrics",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    logger.error(
        "Unhandled exception",
        error=str(exc),
        path=request.url.path,
        method=request.method,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )

