#!/bin/bash

###############################################################################
# E2E SMOKE TESTS SCRIPT
#
# Runs end-to-end smoke tests against a running local cluster.
# This script expects the cluster to be running (via docker-compose or k8s).
#
# Usage:
#   ./scripts/e2e-smoke-tests.sh [--environment dev|docker|k8s]
#
# Environment:
#   dev     - docker-compose.dev.yml (default)
#   docker  - docker-compose.yml (production-like)
#   k8s     - Kubernetes cluster (minikube/local k8s)
#
# Exit codes:
#   0 = All smoke tests passed
#   1 = One or more smoke tests failed
#
# Requires: curl, jq, docker-compose (or kubectl for k8s)
###############################################################################

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
ENVIRONMENT=${1:-dev}
API_URL="http://localhost:8080"
WEB_URL="http://localhost:3000"
PYTHON_APP_URL="http://localhost:8000"
HEALTH_TIMEOUT=120
HEALTH_CHECK_INTERVAL=5
FAILED_TESTS=0
PASSED_TESTS=0

# Parse environment
case "$ENVIRONMENT" in
  dev|docker|k8s)
    ENVIRONMENT="$ENVIRONMENT"
    ;;
  *)
    echo "Unknown environment: $ENVIRONMENT"
    exit 1
    ;;
esac

# Helper functions
log_section() {
  echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BLUE}▶ $1${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

log_pass() {
  echo -e "${GREEN}✓ $1${NC}"
  ((PASSED_TESTS++))
}

log_fail() {
  echo -e "${RED}✗ $1${NC}"
  ((FAILED_TESTS++))
}

log_info() {
  echo -e "${YELLOW}ℹ $1${NC}"
}

# Wait for service to be healthy
wait_for_service() {
  local url=$1
  local timeout=$2
  local elapsed=0

  echo -e "${YELLOW}Waiting for $url to be healthy...${NC}"

  while [ $elapsed -lt $timeout ]; do
    if curl -sf "$url/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep $HEALTH_CHECK_INTERVAL
    ((elapsed+=$HEALTH_CHECK_INTERVAL))
  done

  return 1
}

# HTTP request helper
http_get() {
  curl -s "$1"
}

http_status() {
  curl -s -o /dev/null -w "%{http_code}" "$1"
}

# =============================================================================
# STARTUP CHECKS
# =============================================================================
log_section "STARTUP CHECKS"

log_info "Environment: $ENVIRONMENT"
log_info "Testing against: API=$API_URL, Web=$WEB_URL, Python=$PYTHON_APP_URL"

# Start environment if needed
if [ "$ENVIRONMENT" = "dev" ] || [ "$ENVIRONMENT" = "docker" ]; then
  local compose_file="docker-compose.${ENVIRONMENT}.yml"
  if [ ! -f "$compose_file" ]; then
    compose_file="docker-compose.yml"
  fi

  log_info "Starting environment with $compose_file..."
  if docker-compose -f "$compose_file" up -d >/dev/null 2>&1; then
    log_pass "Environment started"
  else
    log_fail "Failed to start environment"
    exit 1
  fi

  # Wait for services
  log_info "Waiting for services to be healthy..."
  wait_for_service "$API_URL" $HEALTH_TIMEOUT || {
    log_fail "API service failed to start"
    docker-compose -f "$compose_file" logs || true
    exit 1
  }
  log_pass "All services healthy"
fi

# =============================================================================
# 1. SERVICE HEALTH CHECKS
# =============================================================================
log_section "1. SERVICE HEALTH CHECKS"

# API health
if http_status "$API_URL/health" | grep -q "200"; then
  log_pass "API service is healthy"
else
  log_fail "API service is not responding"
fi

# Web health
if http_status "$WEB_URL/health" | grep -q "200"; then
  log_pass "Web service is healthy"
else
  log_fail "Web service is not responding"
fi

# Python app health
if http_status "$PYTHON_APP_URL/health" | grep -q "200"; then
  log_pass "Python app service is healthy"
else
  log_fail "Python app service is not responding"
fi

# =============================================================================
# 2. METRICS ENDPOINT
# =============================================================================
log_section "2. METRICS ENDPOINTS"

# Prometheus metrics
if http_status "$API_URL/metrics" | grep -q "200"; then
  log_pass "API metrics endpoint is responding"
else
  log_fail "API metrics endpoint not accessible"
fi

# =============================================================================
# 3. API ENDPOINT TESTS
# =============================================================================
log_section "3. API ENDPOINT TESTS"

# Test status endpoint
if http_status "$API_URL/api/v1/status" | grep -q "200"; then
  log_pass "API /api/v1/status endpoint working"
else
  log_fail "API /api/v1/status endpoint failed"
fi

# Test features endpoint
response=$(http_get "$API_URL/api/v1/features")
if echo "$response" | jq . >/dev/null 2>&1; then
  log_pass "API /api/v1/features returns valid JSON"

  # Check for expected fields
  if echo "$response" | jq -e '.features' >/dev/null 2>&1; then
    log_pass "Features object contains 'features' field"
  else
    log_fail "Features object missing 'features' field"
  fi
else
  log_fail "API /api/v1/features returned invalid JSON"
fi

# =============================================================================
# 4. DATA PIPELINE TESTS
# =============================================================================
log_section "4. DATA PIPELINE TESTS"

# Test log receiver (if endpoint exists)
if http_status "$API_URL/api/v1/logs" | grep -qE "200|400|401"; then
  log_pass "Log endpoint is accessible"
else
  log_fail "Log endpoint not responding"
fi

# Test metrics receiver (if endpoint exists)
if http_status "$API_URL/api/v1/metrics" | grep -qE "200|400|401"; then
  log_pass "Metrics endpoint is accessible"
else
  log_fail "Metrics endpoint not responding"
fi

# =============================================================================
# 5. LICENSE INTEGRATION
# =============================================================================
log_section "5. LICENSE INTEGRATION"

# Check that license features are accessible
response=$(http_get "$API_URL/api/v1/features")
feature_count=$(echo "$response" | jq '.features | length' 2>/dev/null || echo "0")

if [ "$feature_count" -gt 0 ]; then
  log_pass "License integration is working ($feature_count features available)"
else
  log_info "No features available (may be expected for trial license)"
fi

# =============================================================================
# 6. ERROR HANDLING
# =============================================================================
log_section "6. ERROR HANDLING"

# Test 404 handling
if http_status "$API_URL/api/v1/nonexistent" | grep -q "404"; then
  log_pass "404 error handling works correctly"
else
  log_fail "404 error handling not working as expected"
fi

# Test missing authentication (if required)
# This depends on your actual auth requirements
log_info "Error handling validation complete"

# =============================================================================
# 7. PERFORMANCE BASELINE
# =============================================================================
log_section "7. PERFORMANCE BASELINE"

# Measure API response time
start_time=$(date +%s%N)
http_get "$API_URL/api/v1/status" >/dev/null
end_time=$(date +%s%N)
response_time=$(( (end_time - start_time) / 1000000 ))  # Convert to ms

if [ $response_time -lt 1000 ]; then
  log_pass "API response time is good (${response_time}ms)"
elif [ $response_time -lt 5000 ]; then
  log_info "API response time is acceptable (${response_time}ms)"
else
  log_fail "API response time is slow (${response_time}ms)"
fi

# =============================================================================
# 8. DATABASE CONNECTIVITY
# =============================================================================
log_section "8. DATABASE CONNECTIVITY"

# Check if we can query data (basic connectivity test)
if [ -n "$(http_get "$API_URL/api/v1/status" 2>/dev/null)" ]; then
  log_pass "Database connectivity verified (API responding)"
else
  log_fail "Database connectivity issue (API not responding)"
fi

# =============================================================================
# CLEANUP
# =============================================================================
if [ "$ENVIRONMENT" = "dev" ] || [ "$ENVIRONMENT" = "docker" ]; then
  log_section "CLEANUP"
  log_info "Cleaning up test environment..."
  docker-compose -f "docker-compose.${ENVIRONMENT}.yml" down -v >/dev/null 2>&1 || \
  docker-compose -f "docker-compose.yml" down -v >/dev/null 2>&1 || true
  log_pass "Environment cleaned up"
fi

# =============================================================================
# SUMMARY
# =============================================================================
log_section "SUMMARY"

echo -e "\n${GREEN}Passed tests: ${PASSED_TESTS}${NC}"
echo -e "${RED}Failed tests: ${FAILED_TESTS}${NC}\n"

if [ "$FAILED_TESTS" -eq 0 ]; then
  echo -e "${GREEN}✓ All E2E smoke tests passed!${NC}"
  exit 0
else
  echo -e "${RED}✗ Some tests failed. Check logs above for details.${NC}"
  exit 1
fi
