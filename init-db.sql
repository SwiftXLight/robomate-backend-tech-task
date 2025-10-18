-- Initialize TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create events table
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL,
    event_id UUID NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    properties JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id, occurred_at)
);

-- Create unique constraint for idempotency
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_event_id ON events (event_id);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_events_user_id ON events (user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON events (event_type, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_occurred_at ON events (occurred_at DESC);

-- Create GIN index for JSONB properties (for filtering)
CREATE INDEX IF NOT EXISTS idx_events_properties ON events USING GIN (properties);

-- Convert to hypertable (TimescaleDB)
SELECT create_hypertable('events', 'occurred_at', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Create continuous aggregate for Daily Active Users (DAU)
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_active_users
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', occurred_at) AS day,
    COUNT(DISTINCT user_id) AS active_users
FROM events
GROUP BY day
WITH NO DATA;

-- Refresh policy for DAU aggregate
SELECT add_continuous_aggregate_policy('daily_active_users',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Create continuous aggregate for Event Type counts
CREATE MATERIALIZED VIEW IF NOT EXISTS event_type_counts
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', occurred_at) AS day,
    event_type,
    COUNT(*) AS event_count
FROM events
GROUP BY day, event_type
WITH NO DATA;

-- Refresh policy for event type counts
SELECT add_continuous_aggregate_policy('event_type_counts',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Initial refresh of continuous aggregates
CALL refresh_continuous_aggregate('daily_active_users', NULL, NULL);
CALL refresh_continuous_aggregate('event_type_counts', NULL, NULL);

-- Create retention policy (optional - keep data for 1 year)
-- SELECT add_retention_policy('events', INTERVAL '365 days', if_not_exists => TRUE);

COMMENT ON TABLE events IS 'Main events table with TimescaleDB hypertable for time-series optimization';
COMMENT ON COLUMN events.event_id IS 'Unique identifier for idempotency';
COMMENT ON COLUMN events.properties IS 'Flexible JSONB field for event-specific properties';

