# Event Analytics Service

A high-performance event ingestion and analytics service built with FastAPI, TimescaleDB, Redis, and NATS JetStream.

## Architecture

This service implements an event-driven architecture for ingesting and analyzing user events:

- **FastAPI**: Async web framework for high-throughput API
- **PostgreSQL + TimescaleDB**: Time-series optimized database for event storage
- **Redis**: Idempotency checking and rate limiting
- **NATS JetStream**: Async message queue for event processing
- **Prometheus**: Metrics collection and monitoring

## Features

✅ **Event Ingestion**: Batch event ingestion with validation and idempotency  
✅ **Analytics Endpoints**: DAU, top events, cohort retention analysis  
✅ **Async Processing**: NATS JetStream for reliable event processing  
✅ **Idempotency**: Duplicate event detection using Redis  
✅ **Rate Limiting**: Token bucket rate limiter  
✅ **Observability**: Structured logging and Prometheus metrics  
✅ **CSV Import**: CLI tool for bulk historical data import  
✅ **Tests**: Unit and integration tests with pytest  

## Quick Start

### Prerequisites

- Docker & Docker Compose
- (Optional) Python 3.11+ with Poetry for local development

### Run with Docker

```bash
# Start all services
docker-compose up --build

# The API will be available at:
# - API: http://localhost:8000
# - Docs: http://localhost:8000/docs
# - Metrics: http://localhost:8000/metrics
# - NATS: http://localhost:8222 (monitoring)
```

### Run Locally (Development)

```bash
# Install dependencies
poetry install

# Start infrastructure services only
docker-compose up timescaledb redis nats

# Run API server
poetry run uvicorn app.main:app --reload

# Start worker in another terminal
poetry run python -m app.workers.event_processor
```

## API Endpoints

### Event Ingestion

```bash
# Ingest events (batch)
POST /events
Content-Type: application/json

{
  "events": [
    {
      "event_id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "user_123",
      "event_type": "page_view",
      "occurred_at": "2024-01-15T10:30:00Z",
      "properties": {
        "page": "/home",
        "duration": 5.2
      }
    }
  ]
}
```

### Analytics

```bash
# Daily Active Users
GET /stats/dau?from=2024-01-01&to=2024-01-31

# Top Events
GET /stats/top-events?from=2024-01-01&to=2024-01-31&limit=10

# Cohort Retention
GET /stats/retention?start_date=2024-01-01&windows=3&window_type=daily
```

### Health & Metrics

```bash
# Health check
GET /health

# Prometheus metrics
GET /metrics
```

## Import Historical Data

```bash
# Using Docker
docker-compose exec api python -m scripts.import_events /app/data/events_sample.csv

# Or locally
poetry run python -m scripts.import_events data/events_sample.csv
```

CSV format:
```csv
event_id,occurred_at,user_id,event_type,properties_json
550e8400-e29b-41d4-a716-446655440000,2024-01-15T10:30:00Z,user_123,page_view,"{""page"": ""/home""}"
```

## Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=app --cov-report=html

# Run specific test file
poetry run pytest tests/unit/test_idempotency.py -v

# Run integration tests only
poetry run pytest tests/integration/ -v
```

## Performance & Benchmarking

### Methodology

Benchmarked on:
- **Hardware**: [To be measured]
- **Method**: Locust for load testing
- **Scenario**: Ingest 100,000 events in batches of 100

### Results

```
[To be benchmarked]
Events ingested: 100,000
Time taken: X seconds
Events per second: Y
Average latency: Z ms
```

### Bottlenecks Identified

1. **Database Write Throughput**: 
   - Current: Single-node PostgreSQL
   - Solution: Connection pooling, batch inserts, consider read replicas

2. **Redis Idempotency Checks**:
   - Current: Pipeline operations implemented
   - Solution: Consider bloom filters for scale

3. **NATS Message Processing**:
   - Current: Single worker
   - Solution: Multiple workers, batch processing from queue

### Scalability Improvements

- **Horizontal Scaling**: Deploy multiple API instances behind load balancer
- **Database**: Add read replicas for analytics queries, partition by time
- **Caching**: Cache aggregated statistics with TTL
- **Cold Storage**: Implement hot/cold architecture with DuckDB + Parquet for old data
- **Batch Processing**: Process events in larger batches from NATS

## Project Structure

```
.
├── app/
│   ├── api/                 # API routes and middleware
│   │   ├── routes/
│   │   │   ├── events.py    # Event ingestion endpoint
│   │   │   ├── stats.py     # Analytics endpoints
│   │   │   └── health.py    # Health checks
│   │   ├── dependencies.py  # FastAPI dependencies
│   │   └── middleware.py    # Custom middleware
│   ├── core/                # Core utilities
│   │   ├── config.py        # Configuration
│   │   ├── logging.py       # Structured logging
│   │   └── metrics.py       # Prometheus metrics
│   ├── db/                  # Database
│   │   └── database.py      # Connection management
│   ├── models/              # Pydantic models
│   │   └── event.py         # Event schemas
│   ├── services/            # Business logic
│   │   ├── event_service.py # Event operations
│   │   ├── redis_service.py # Idempotency & rate limiting
│   │   └── nats_service.py  # Message queue
│   ├── workers/             # Background workers
│   │   └── event_processor.py # NATS consumer
│   └── main.py              # FastAPI application
├── scripts/
│   └── import_events.py     # CSV import CLI
├── tests/
│   ├── unit/                # Unit tests
│   └── integration/         # Integration tests
├── data/                    # Data files
│   └── events_sample.csv
├── docker-compose.yml       # Docker services
├── Dockerfile               # Application container
├── pyproject.toml           # Dependencies
├── init-db.sql              # Database schema
├── ADR.md                   # Architecture decisions
└── LEARNED.md               # Learning notes (NATS)
```

## Configuration

Environment variables (create `.env` file, see docker-compose.yml for defaults):

```bash
# Database
POSTGRES_DB=events_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DATABASE_URL=postgresql+asyncpg://postgres:postgres@timescaledb:5432/events_db

# Redis
REDIS_URL=redis://redis:6379

# NATS
NATS_URL=nats://nats:4222

# Application
ENVIRONMENT=development
LOG_LEVEL=INFO
RATE_LIMIT_REQUESTS=1000
RATE_LIMIT_WINDOW=60
```

## Monitoring

### Structured Logs

JSON-formatted logs with context:
```json
{
  "event": "Events accepted for processing",
  "accepted": 100,
  "duplicates": 5,
  "duration_seconds": 0.234,
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "info"
}
```

### Metrics

Key Prometheus metrics:
- `events_received_total` - Total events received (by type)
- `events_ingested_total` - Successfully ingested events
- `events_duplicate_total` - Duplicate events detected
- `ingestion_duration_seconds` - Ingestion latency histogram
- `api_requests_total` - API requests (by endpoint, status)
- `rate_limit_exceeded_total` - Rate limit violations

View metrics: http://localhost:8000/metrics

## Development

### Code Quality

```bash
# Format code
poetry run black app/ tests/

# Lint
poetry run ruff check app/ tests/

# Type checking
poetry run mypy app/
```

## Production Considerations

### Security

- [ ] Enable API key authentication
- [ ] Add HTTPS/TLS termination
- [ ] Implement request signing
- [ ] Add input sanitization
- [ ] Enable CORS properly
- [ ] Use secrets management (Vault, AWS Secrets Manager)

### Reliability

- [ ] Add circuit breakers
- [ ] Implement retry logic with exponential backoff
- [ ] Add dead letter queue monitoring
- [ ] Set up alerting (PagerDuty, Slack)
- [ ] Database backups and replication

### Performance

- [ ] Enable query result caching
- [ ] Add database read replicas
- [ ] Optimize continuous aggregates refresh
- [ ] Implement hot/cold storage (DuckDB + Parquet)

## License

MIT
