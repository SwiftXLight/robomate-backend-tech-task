# What I Learned About NATS JetStream

## What is NATS JetStream?

NATS JetStream is a distributed persistence layer built on top of NATS Core messaging system. It provides message streaming, persistence, and delivery guarantees that are essential for building reliable event-driven architectures.

## Why I Chose NATS JetStream

1. **Lightweight**: Much simpler to deploy than Kafka (no Zookeeper/KRaft required)
2. **Docker-friendly**: Single container with minimal configuration
3. **Modern**: Built with cloud-native principles
4. **Learning opportunity**: Wanted to explore alternatives to RabbitMQ/Kafka

## Key Concepts Learned

### 1. Streams vs Subjects

- **Subjects**: Topic-like routing keys (e.g., `events.ingest`, `events.failed`)
- **Streams**: Persistent storage layer that captures messages on subjects
- Streams can capture multiple related subjects using wildcards (`events.*`)

```python
# Creating a stream
await jetstream.add_stream(
    StreamConfig(
        name="EVENTS",
        subjects=["events.>"],  # Captures events.ingest, events.retry, etc.
        retention=RetentionPolicy.WORK_QUEUE,  # Messages deleted after ack
        storage=StorageType.FILE,  # Persistent on disk
    )
)
```

### 2. Consumers and Pull Subscriptions

NATS has two consumer types:
- **Push consumers**: Server pushes messages to clients
- **Pull consumers**: Clients request batches of messages

I used **pull subscriptions** because:
- Better control over processing rate
- Can batch-fetch messages
- Good for worker patterns

```python
# Pull subscribe
subscription = await js.pull_subscribe(
    subject="events.ingest",
    durable="event-processor",  # Durable = survives restarts
    config=ConsumerConfig(
        ack_policy=AckPolicy.EXPLICIT,  # Manual ack
        max_deliver=3,  # Retry up to 3 times
        ack_wait=30,  # Wait 30s for ack before redelivery
    ),
)

# Fetch messages
messages = await subscription.fetch(batch=10, timeout=1.0)
```

### 3. Acknowledgment Modes

JetStream supports different ack patterns:

| Mode | Description | Use Case |
|------|-------------|----------|
| `ack()` | Success, message processed | Normal flow |
| `nak()` | Failure, redeliver | Temporary error, retry |
| `term()` | Terminate, don't redeliver | Permanent error (bad data) |
| `in_progress()` | Still processing, extend timeout | Long-running task |

```python
try:
    await process_event(msg)
    await msg.ack()  # Success
except ValidationError:
    await msg.term()  # Bad data, don't retry
except TemporaryError:
    await msg.nak(delay=5)  # Retry after 5 seconds
```

### 4. Durable Consumers

Durable consumers persist their state (which messages were acked):
- Consumer survives worker restarts
- Multiple workers can use same durable name (load balancing)
- Tracks progress automatically

```python
consumer_config = ConsumerConfig(
    durable_name="event-processor",  # Name identifies the consumer
    ack_policy=AckPolicy.EXPLICIT,
)
```

### 5. Retention Policies

- **Limits**: Keep messages until storage/message/age limits
- **Interest**: Keep until all consumers ack
- **WorkQueue**: Delete after any consumer acks (best for task queues)

I chose `WorkQueue` because events should be processed once and deleted.

### 6. Message Persistence

JetStream can use:
- **File storage**: Persisted to disk (slower, durable)
- **Memory storage**: In-memory only (faster, volatile)

I used file storage for durability:
```python
storage=StorageType.FILE
```

## Challenges Encountered

### 1. Stream Already Exists Error

**Problem**: Re-creating a stream that already exists throws an error.

**Solution**: 
```python
try:
    await jetstream.add_stream(config)
except Exception:
    # Stream might exist, that's okay
    pass
```

Or use `update_stream()` for idempotency.

### 2. Understanding Pull vs Push

**Initially**: Tried push subscriptions, but had issues with backpressure control.

**Solution**: Switched to pull subscriptions for better control:
- Worker decides when to fetch more messages
- Can implement custom batch processing
- Better for CPU-bound processing

### 3. Timeout Handling

**Problem**: `fetch()` times out when no messages available (throws exception).

**Solution**: Catch `TimeoutError` and continue polling:
```python
while not shutdown:
    try:
        messages = await subscription.fetch(batch=10, timeout=1.0)
        for msg in messages:
            await process(msg)
    except TimeoutError:
        continue  # No messages, keep polling
```

## Comparison with Other Message Brokers

### vs RabbitMQ
- **NATS**: Simpler, faster, less features
- **RabbitMQ**: More mature, complex routing, heavier

### vs Kafka
- **NATS**: Much simpler deployment, less operational overhead
- **Kafka**: Better for massive scale, more ecosystem tools

### vs Redis Streams
- **NATS**: Purpose-built for messaging, better guarantees
- **Redis**: Lighter, but not designed as primary message broker

## Best Practices I Learned

1. **Use durable consumers**: Survive restarts, track progress
2. **Set `max_deliver`**: Prevent infinite retry loops
3. **Choose right ack policy**: `EXPLICIT` for control, `ALL` for simplicity
4. **Batch fetch**: More efficient than one-at-a-time
5. **Handle timeouts gracefully**: Empty queue is normal
6. **Use file storage**: For durability in production
7. **Monitor stream metrics**: Use NATS monitoring endpoint (`:8222/varz`)

## Configuration I Used

```yaml
nats:
  image: nats:latest
  command:
    - "--jetstream"           # Enable JetStream
    - "--store_dir=/data"     # Persistence directory
    - "--max_payload=10MB"    # Large messages support
    - "--max_mem=2G"          # Memory limit
  ports:
    - "4222:4222"  # Client connections
    - "8222:8222"  # HTTP monitoring
  volumes:
    - nats_data:/data
```

## Monitoring

NATS provides built-in monitoring at `:8222`:
- `/varz` - Server info, memory, connections
- `/connz` - Active connections
- `/subsz` - Subscriptions
- `/jsz` - JetStream info

Can be scraped by Prometheus.

## What I Would Do Differently

1. **Use NATS CLI tools**: `nats` CLI is very helpful for debugging streams
2. **Add dead letter queue**: For permanently failed messages
3. **Implement backoff strategy**: Exponential backoff for retries
4. **Add monitoring dashboard**: Grafana dashboard for NATS metrics
5. **Consider NATS KV**: For distributed configuration/state

## Resources That Helped

- [NATS JetStream Documentation](https://docs.nats.io/nats-concepts/jetstream)
- [nats-py Examples](https://github.com/nats-io/nats.py/tree/main/examples)
- [JetStream Architecture](https://docs.nats.io/nats-concepts/jetstream/js_walkthrough)
- [Python async client guide](https://nats-io.github.io/nats.py/)

## Conclusion

NATS JetStream is an excellent choice for this project:
- ✅ Easy to deploy and configure
- ✅ Reliable with persistence and ack guarantees
- ✅ Good performance for event streaming
- ✅ Simple mental model (simpler than Kafka)
- ✅ Lightweight resource usage

For a take-home project and learning exercise, it strikes the perfect balance between simplicity and capability. In production, I would add:
- Multiple NATS servers (clustering)
- Better monitoring and alerting
- Dead letter queue handling
- Rate limiting on consumer side

Overall, a great tool to have in the toolkit for event-driven architectures!
