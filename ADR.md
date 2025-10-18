# Архітектурні Рішення: Сервіс Інгесту Подій та Аналітики

## 1. Веб-фреймворк

### Контекст
Потрібен швидкий, асинхронний фреймворк для обробки великої кількості подій (100k+ events) з підтримкою валідації даних та автоматичною документацією API.

### Варіанти
- **FastAPI (Python)**: Async/await, Pydantic валідація, автоматична OpenAPI документація, швидка розробка
- **Actix-web (Rust)**: Максимальна продуктивність, але довша розробка та складніша інтеграція з data tools
- **Gin (Go)**: Хороша продуктивність та concurrency, але менше бібліотек для аналітики
- **Express.js/Fastify (Node.js)**: Швидка розробка, але менш придатний для data-heavy операцій

### Рішення: **FastAPI**
- Відповідає вимогам вакансії (Python Backend)
- Async підтримка критична для high-throughput event ingestion
- Pydantic забезпечує надійну валідацію вхідних даних
- Швидка розробка дозволяє зосередитись на архітектурі та оптимізації
- Велика екосистема Python для роботи з даними та тестування

---

## 2. База Даних

### Контекст
Потрібно зберігати події з timestamps, забезпечити ідемпотентність, виконувати аналітичні запити (DAU, top events, retention cohorts), обробляти 100k+ подій.

### Варіанти

**A. PostgreSQL + TimescaleDB (single solution)**
- ✅ Time-series оптимізація (hypertables, automatic partitioning)
- ✅ ACID транзакції для надійного інгесту
- ✅ JSONB з GIN індексами для flexible properties
- ✅ Continuous aggregates для pre-computed metrics
- ✅ Mature, production-ready
- ❌ Не є "новим інструментом" для вивчення

**B. TimescaleDB (hot) + DuckDB (cold) - Hot/Cold Architecture**
- ✅ TimescaleDB для real-time даних (останні 30 днів)
- ✅ DuckDB для аналітики historical даних (Parquet files)
- ✅ Вивчення DuckDB як нового інструменту
- ✅ Демонструє розуміння cost-effective storage patterns
- ✅ DuckDB надзвичайно швидкий для OLAP запитів
- ❌ Більш складна реалізація (потрібен data migration job)
- ❌ Query logic має перевіряти обидва джерела

**C. DuckDB Only**
- ✅ Embedded DB, простий deployment
- ✅ Відмінна продуктивність для аналітики
- ❌ Single-writer обмеження (проблема для concurrent writes)
- ❌ Менш mature для high-write scenarios
- ❌ Ризиковано для production-like системи

**D. ClickHouse**
- ✅ Industry standard для event analytics
- ✅ Найкраща продуктивність для цього use case
- ❌ No transactions (eventual consistency)
- ❌ Updates складні (ідемпотентність потребує ретельної реалізації)
- ❌ Більш resource-intensive

### Рішення: **PostgreSQL + TimescaleDB (з опціональним DuckDB для cold storage)**

**Фаза 1 (Core MVP)**: PostgreSQL + TimescaleDB
- Фокус на solid execution та швидкій реалізації всіх вимог
- TimescaleDB забезпечує оптимізацію для time-series даних
- Hypertables для автоматичного partitioning по часу
- Continuous aggregates для pre-computed метрик (DAU, top events)
- JSONB з GIN індексами для гнучких запитів до properties
- Надійна ідемпотентність через UNIQUE constraint на event_id
- NATS JetStream виступає як "новий інструмент" для вивчення

**Фаза 2 (Optional Enhancement)**: Додати DuckDB + Parquet
- Якщо залишиться час після core функціональності
- Background job для експорту старих даних (>30 днів) в Parquet
- DuckDB для швидких аналітичних запитів по historical data
- Демонструє розуміння hot/cold storage patterns
- Другий "новий інструмент" для вивчення

**Обґрунтування**:
- Balanced approach: production-ready core + опція для sophistication
- Мінімізує ризики: TimescaleDB mature і надійний
- Flexibility: можна почати просто, розширити пізніше
- Focus: більше часу на NATS, тестування, observability, benchmarking
- Interview-ready: є що розповісти про trade-offs і рішення

---

## 3. Message Queue

### Контекст
Опціональне розширення: асинхронний інгест через брокер з retry mechanism та dead-letter queue.

### Варіанти
- **NATS JetStream**: Легкий, швидкий, at-least-once/exactly-once delivery, простий deployment
- **RabbitMQ**: Mature, гарне tooling, але повільніший та складніший setup
- **Apache Kafka**: Industry standard, але overkill для цього масштабу
- **Redis Streams**: Простий, але обмежені можливості порівняно з dedicated brokers

### Рішення: **NATS JetStream**
- Новий інструмент для вивчення (відповідає вимозі завдання)
- Легкий та швидкий - підходить для Docker deployment
- Має persistence layer (JetStream) для надійності
- Consumer groups та retry logic з коробки
- Хороша продуктивність для event streaming

---

## 4. Кешування та Ідемпотентність

### Контекст
Потрібно швидко перевіряти `event_id` для запобігання дублікатів, реалізувати rate limiting.

### Варіанти
- **Redis**: Швидкий, atomic operations, можна використати для кількох цілей
- **In-memory cache**: Простіше, але втрачається при перезапуску
- **Database-only**: Повільніше для high-throughput scenarios

### Рішення: **Redis**
- Sub-millisecond latency для idempotency checks
- SET NX для atomic перевірки унікальності event_id
- Token bucket для rate limiting
- Можна використати для інших кешів (aggregated metrics)

---

## 5. Тестування

### Контекст
Потрібні unit тести для ідемпотентності, інтеграційні тести для повного flow "інгест → запит статистики".

### Варіанти
- **pytest**: Стандарт для Python, багата екосистема плагінів
- **unittest**: Вбудований, але менш зручний
- **Robot Framework**: Для E2E, але overkill

### Рішення: **pytest + pytest-asyncio + httpx**
- pytest-asyncio для тестування async endpoints
- httpx для HTTP client testing
- pytest-cov для code coverage
- Factory fixtures для test data
- Можливість легко створити інтеграційні тести з Docker контейнерами

---

## 6. Observability

### Контекст
Потрібні структуровані логи та метрики (events/sec, response time).

### Варіанти
- **Prometheus + Grafana**: Industry standard, але потребує окремих сервісів
- **OpenTelemetry**: Vendor-neutral, але складніший setup
- **Structured logging + metrics library**: Простіше, lightweight

### Рішення: **structlog + prometheus-client**
- structlog для structured JSON logs (легко парсити)
- prometheus-client для метрик (Counter, Histogram, Gauge)
- Метрики: events_ingested_total, ingestion_duration_seconds, api_requests_total
- Логи з context (request_id, user_id, event_type)
- Можна легко інтегрувати з Grafana пізніше

---

## 7. Rate Limiting

### Контекст
Базовий rate limiting для захисту від abuse.

### Варіанти
- **In-memory token bucket**: Простий, але не працює з multiple instances
- **Redis-based**: Shared state, persistent
- **slowapi (FastAPI middleware)**: Ready-to-use, але використовує Redis

### Рішення: **Redis-based Token Bucket**
- Використовуємо існуючий Redis
- Atomic operations з INCR та EXPIRE
- Configurable limits (напр., 1000 req/min per IP)
- Graceful handling з 429 Too Many Requests

---

## Фінальна Архітектура

```
┌─────────┐
│ Client  │
└────┬────┘
     │ POST /events (batch)
     ▼
┌─────────────────┐
│    FastAPI      │◄─── Rate Limiting (Redis)
│   + Pydantic    │
└────┬────────────┘
     │
     ├─► Redis (idempotency check)
     │
     ├─► NATS JetStream (async processing)
     │        │
     ▼        ▼
┌──────────────────┐      ┌────────────┐
│  TimescaleDB     │◄─────│   Worker   │
│  (events table)  │      └────────────┘
└──────────────────┘
     │
     │ (optional: background job)
     ▼
┌──────────────────┐
│ Parquet + DuckDB │
│  (cold storage)  │
└──────────────────┘

GET /stats/* → Query TimescaleDB (+ DuckDB if cold data needed)
```

---

## Обґрунтування Складності

Архітектура балансує між:
1. **Production-readiness**: TimescaleDB, Redis, NATS - mature tools
2. **Learning opportunity**: NATS JetStream (новий інструмент)
3. **Scalability**: Async ingestion, message queue, optional hot/cold storage
4. **Maintainability**: Python ecosystem, structured logs, metrics
5. **Performance**: Column-store benefits, pre-aggregation, efficient indexing