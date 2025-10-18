"""Prometheus metrics configuration."""

from prometheus_client import Counter, Histogram, Gauge

# Event ingestion metrics
events_received_total = Counter(
    "events_received_total",
    "Total number of events received",
    ["event_type"],
)

events_ingested_total = Counter(
    "events_ingested_total",
    "Total number of events successfully ingested",
    ["event_type"],
)

events_duplicate_total = Counter(
    "events_duplicate_total",
    "Total number of duplicate events (idempotency)",
)

events_failed_total = Counter(
    "events_failed_total",
    "Total number of events that failed to ingest",
    ["reason"],
)

# Processing time metrics
ingestion_duration_seconds = Histogram(
    "ingestion_duration_seconds",
    "Time spent ingesting events",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0],
)

# API metrics
api_requests_total = Counter(
    "api_requests_total",
    "Total number of API requests",
    ["method", "endpoint", "status_code"],
)

api_request_duration_seconds = Histogram(
    "api_request_duration_seconds",
    "API request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# System metrics
active_connections = Gauge(
    "active_connections",
    "Number of active database connections",
)

queue_depth = Gauge(
    "queue_depth",
    "Number of messages in NATS queue",
)

# Rate limiting
rate_limit_exceeded_total = Counter(
    "rate_limit_exceeded_total",
    "Total number of rate limit exceeded events",
    ["client_ip"],
)

