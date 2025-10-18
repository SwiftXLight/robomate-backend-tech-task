# Quick Start Guide

## Prerequisites

- Docker and Docker Compose installed
- (Optional) Python 3.11+ and Poetry for local development

## 5-Minute Setup

### 1. Start Services

```bash
# Start all services (API, Worker, Database, Redis, NATS)
docker-compose up --build
```

Wait for all services to be healthy (check with `docker-compose ps`).

### 2. Verify Services

```bash
# Check health
curl http://localhost:8000/health

# View API docs
open http://localhost:8000/docs
```

### 3. Import Sample Data

```bash
# Import CSV data
docker-compose exec api python -m scripts.import_events /app/data/events_sample.csv
```

### 4. Test Event Ingestion

```bash
# Ingest a test event
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {
        "event_id": "123e4567-e89b-12d3-a456-426614174000",
        "user_id": "test_user",
        "event_type": "test_event",
        "occurred_at": "2024-01-15T12:00:00Z",
        "properties": {"test": true}
      }
    ]
  }'
```

### 5. Query Analytics

```bash
# Get Daily Active Users
curl "http://localhost:8000/stats/dau?from=2024-01-15&to=2024-01-16"

# Get Top Events
curl "http://localhost:8000/stats/top-events?from=2024-01-15&to=2024-01-16&limit=5"

# Get Retention
curl "http://localhost:8000/stats/retention?start_date=2024-01-15&windows=2"
```

### 6. View Metrics

```bash
# Prometheus metrics
curl http://localhost:8000/metrics

# NATS monitoring
open http://localhost:8222
```

## Using Makefile (Convenience)

```bash
# Show all available commands
make help

# Start services
make up

# View logs
make logs

# Run tests
make test

# Import sample data
make import-sample

# Check API health
make health
```

## Architecture Overview

```
Client Request
     │
     ▼
┌─────────────┐
│  FastAPI    │ ◄── Rate Limiting (Redis)
│  (Port 8000)│
└─────┬───────┘
      │
      ├─► Redis (idempotency check)
      │
      ├─► NATS JetStream (async queue)
      │        │
      │        ▼
      │   ┌────────────┐
      │   │   Worker   │
      │   └─────┬──────┘
      │         │
      ▼         ▼
┌────────────────────┐
│   TimescaleDB      │
│   (Port 5432)      │
└────────────────────┘
```

## Service Ports

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Metrics**: http://localhost:8000/metrics
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379
- **NATS Client**: localhost:4222
- **NATS Monitoring**: http://localhost:8222

## Common Commands

### Docker

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down

# Rebuild after code changes
docker-compose up --build
```

### Database

```bash
# Access PostgreSQL
docker-compose exec timescaledb psql -U postgres -d events_db

# Reset database
docker-compose exec timescaledb psql -U postgres -d events_db -c "TRUNCATE TABLE events CASCADE;"
```

### Local Development

```bash
# Install dependencies
poetry install

# Start infrastructure only
docker-compose up timescaledb redis nats

# Run API locally
poetry run uvicorn app.main:app --reload

# Run worker locally (in another terminal)
poetry run python -m app.workers.event_processor

# Run tests
poetry run pytest -v
```

## Troubleshooting

### Services won't start

```bash
# Check logs
docker-compose logs

# Check specific service
docker-compose logs api
docker-compose logs timescaledb
```

### Database connection issues

```bash
# Verify database is healthy
docker-compose ps

# Check database logs
docker-compose logs timescaledb

# Verify connection
docker-compose exec timescaledb pg_isready -U postgres
```

### NATS connection issues

```bash
# Check NATS status
curl http://localhost:8222/varz

# View NATS logs
docker-compose logs nats
```

### Port already in use

```bash
# Find process using port 8000
lsof -i :8000

# Or change ports in docker-compose.yml
```

### Clean slate restart

```bash
# Stop and remove everything
docker-compose down -v

# Remove all data
docker volume prune

# Start fresh
docker-compose up --build
```

## Next Steps

1. **Explore API**: Open http://localhost:8000/docs
2. **Run Tests**: `make test` or `poetry run pytest`
3. **Import More Data**: Prepare your own CSV and import it
4. **Monitor**: Check metrics at http://localhost:8000/metrics
5. **Benchmark**: Create load test to measure performance
6. **Extend**: Add new event types, analytics queries, or cold storage

## Development Workflow

1. Make code changes in `app/` directory
2. Changes auto-reload if using `--reload` flag
3. Run tests: `make test`
4. Check logs: `make logs-api`
5. Format code: `make format`
6. Commit changes

## Production Deployment Checklist

- [ ] Set strong passwords in environment variables
- [ ] Enable HTTPS/TLS
- [ ] Configure proper logging level (INFO/WARNING)
- [ ] Set up monitoring and alerting
- [ ] Configure database backups
- [ ] Review and adjust rate limits
- [ ] Enable API authentication
- [ ] Scale workers based on load
- [ ] Set up CI/CD pipeline
- [ ] Load test before going live

## Resources

- **API Documentation**: http://localhost:8000/docs
- **Redoc**: http://localhost:8000/redoc
- **Architecture Decision Record**: [ADR.md](ADR.md)
- **Learning Notes**: [LEARNED.md](LEARNED.md)
- **Full README**: [README.md](README.md)

## Getting Help

If you encounter issues:
1. Check logs: `make logs`
2. Verify health: `make health`
3. Review documentation in README.md
4. Check ADR.md for architecture decisions

