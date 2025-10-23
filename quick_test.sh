#!/bin/bash
set -e

echo "🚀 Quick Test Suite for Event Analytics Service"
echo "================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

test_count=0
pass_count=0

run_test() {
    test_count=$((test_count + 1))
    echo -n "Test $test_count: $1... "
    if eval "$2" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PASS${NC}"
        pass_count=$((pass_count + 1))
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}"
        if [ ! -z "$3" ]; then
            echo -e "  ${YELLOW}Debug: $3${NC}"
        fi
        return 1
    fi
}

echo "📊 Running Infrastructure Tests..."
echo "-----------------------------------"
run_test "API Health" \
    "curl -sf http://localhost:8000/health | grep -q healthy" \
    "Check if API is running: docker compose ps api"

run_test "Database Connection" \
    "docker compose exec -T timescaledb psql -U postgres -d events_db -c 'SELECT 1'" \
    "Check database logs: docker compose logs timescaledb"

run_test "Redis Connection" \
    "docker compose exec -T redis redis-cli PING | grep -q PONG" \
    "Check redis logs: docker compose logs redis"

run_test "NATS Connection" \
    "curl -sf http://localhost:8222/varz | head -1" \
    "Check NATS logs: docker compose logs nats"

echo ""
echo "📥 Running Event Ingestion Tests..."
echo "-----------------------------------"
TEST_UUID=$(uuidgen 2>/dev/null || echo "test-$(date +%s)-$RANDOM")

run_test "Event Ingestion (Single)" \
    "curl -sf -X POST http://localhost:8000/events -H 'Content-Type: application/json' -d '{\"events\":[{\"event_id\":\"$TEST_UUID\",\"user_id\":\"test_user\",\"event_type\":\"test_type\",\"occurred_at\":\"2024-01-20T10:00:00Z\",\"properties\":{\"test\":true}}]}' | grep -q accepted"

# Wait for worker to process
echo -n "Waiting for worker to process events... "
sleep 3
echo "done"

run_test "Event Stored in Database" \
    "docker compose exec -T timescaledb psql -U postgres -d events_db -t -c \"SELECT COUNT(*) FROM events WHERE event_id = '$TEST_UUID'\" | grep -q 1" \
    "Check worker logs: docker compose logs worker"

# Test idempotency
run_test "Idempotency (Duplicate Detection)" \
    "curl -sf -X POST http://localhost:8000/events -H 'Content-Type: application/json' -d '{\"events\":[{\"event_id\":\"$TEST_UUID\",\"user_id\":\"test_user\",\"event_type\":\"test_type\",\"occurred_at\":\"2024-01-20T10:00:00Z\",\"properties\":{\"test\":true}}]}' | grep -q duplicates"

echo ""
echo "📊 Running Analytics Tests..."
echo "-----------------------------------"
run_test "Analytics - DAU Endpoint" \
    "curl -sf 'http://localhost:8000/stats/dau?from=2024-01-01&to=2024-12-31' | python3 -m json.tool" \
    "Check API logs: docker compose logs api"

run_test "Analytics - Top Events Endpoint" \
    "curl -sf 'http://localhost:8000/stats/top-events?from=2024-01-01&to=2024-12-31&limit=10' | python3 -m json.tool"

run_test "Analytics - Retention Endpoint" \
    "curl -sf 'http://localhost:8000/stats/retention?start_date=2024-01-20&windows=2&window_type=daily' | python3 -m json.tool"

echo ""
echo "📈 Running Metrics & Monitoring Tests..."
echo "-----------------------------------"
run_test "Prometheus Metrics" \
    "curl -sf -L http://localhost:8000/metrics | grep -q 'python_info\|process_\|# HELP' || curl -sf http://localhost:8000/metrics/ | grep -q 'python_info\|process_\|# HELP'"

run_test "API Documentation" \
    "curl -sf http://localhost:8000/openapi.json | python3 -m json.tool | head -1"

echo ""
echo "🔍 Checking Service Status..."
echo "-----------------------------------"
run_test "Worker Process Running" \
    "docker compose ps worker | grep -q Up" \
    "Start worker: docker compose up -d worker"

run_test "API Process Running" \
    "docker compose ps api | grep -q Up" \
    "Start API: docker compose up -d api"

echo ""
echo "================================================"
echo -e "Results: ${GREEN}$pass_count${NC}/${test_count} tests passed"
echo ""

if [ $pass_count -eq $test_count ]; then
    echo -e "${GREEN}🎉 All tests passed! Your Event Analytics Service is working perfectly!${NC}"
    echo ""
    echo "📚 Next Steps:"
    echo "  • View API docs: http://localhost:8000/docs"
    echo "  • Import sample data: docker compose exec api python -m scripts.import_events /app/data/events_sample.csv"
    echo "  • View metrics: http://localhost:8000/metrics"
    echo "  • Run full test suite: See TESTING_CHECKLIST.md"
    echo ""
    exit 0
else
    echo -e "${RED}❌ Some tests failed. Please check the debug messages above.${NC}"
    echo ""
    echo "🔧 Troubleshooting:"
    echo "  • Check logs: docker compose logs"
    echo "  • Check status: docker compose ps"
    echo "  • Restart services: docker compose restart"
    echo "  • Full checklist: cat TESTING_CHECKLIST.md"
    echo ""
    exit 1
fi

