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

set +e  # Don't exit on errors - continue testing to see all results

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
ENVIRONMENT=${1:-dev}
HEALTH_TIMEOUT=120
HEALTH_CHECK_INTERVAL=5
FAILED_TESTS=0
PASSED_TESTS=0
USE_COMPOSE=false
USE_K8S=false

# Parse environment and set URLs
case "$ENVIRONMENT" in
  dev|alpha)
    # Local docker-compose testing (alpha)
    USE_COMPOSE=true
    API_URL="http://localhost:8080"
    WEB_URL="http://localhost:3000"
    PYTHON_APP_URL="http://localhost:8000"
    FLASK_BACKEND_URL="http://localhost:5000"
    ;;
  docker)
    # Production-like docker-compose testing
    USE_COMPOSE=true
    API_URL="http://localhost:8080"
    WEB_URL="http://localhost:3000"
    PYTHON_APP_URL="http://localhost:8000"
    FLASK_BACKEND_URL="http://localhost:5000"
    ;;
  k8s|beta|staging)
    # Kubernetes cluster testing (beta/staging)
    USE_K8S=true
    # Get service URLs from kubectl or use provided URLs
    NAMESPACE=${NAMESPACE:-killkrill}
    # Use LB IP to bypass Cloudflare for smoke tests
    # LB IPs: 192.168.7.203, 192.168.7.204
    LB_IP=${LB_IP:-"192.168.7.203"}
    FLASK_BACKEND_URL=${FLASK_BACKEND_URL:-"https://${LB_IP}"}
    WEB_URL=${WEB_URL:-"https://${LB_IP}"}
    API_URL=${API_URL:-"https://${LB_IP}"}
    PYTHON_APP_URL=${PYTHON_APP_URL:-"https://${LB_IP}"}
    CURL_EXTRA_ARGS="-k -H \"Host: killkrill.penguintech.io\""
    ;;
  *)
    echo "Unknown environment: $ENVIRONMENT"
    echo "Valid options: dev, alpha, docker, k8s, beta, staging"
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
  if [ -n "$CURL_EXTRA_ARGS" ]; then
    eval curl -s $CURL_EXTRA_ARGS "$1"
  else
    curl -s "$1"
  fi
}

http_status() {
  if [ -n "$CURL_EXTRA_ARGS" ]; then
    eval curl -s -o /dev/null -w "%{http_code}" $CURL_EXTRA_ARGS "$1"
  else
    curl -s -o /dev/null -w "%{http_code}" "$1"
  fi
}

http_post() {
  local url="$1"
  local data="$2"
  if [ -n "$CURL_EXTRA_ARGS" ]; then
    eval curl -s -X POST $CURL_EXTRA_ARGS -H \"Content-Type: application/json\" -d "'$data'" "$url"
  else
    curl -s -X POST -H "Content-Type: application/json" -d "$data" "$url"
  fi
}

# =============================================================================
# STARTUP CHECKS
# =============================================================================
log_section "STARTUP CHECKS"

log_info "Environment: $ENVIRONMENT"
log_info "Testing against:"
log_info "  - API: $API_URL"
log_info "  - Web: $WEB_URL"
log_info "  - Python: $PYTHON_APP_URL"
log_info "  - Flask Backend: $FLASK_BACKEND_URL"

# Start environment if needed (only for local docker-compose)
if [ "$USE_COMPOSE" = true ]; then
  # Check if services are already running
  if docker ps | grep -q "killkrill-flask-backend"; then
    log_info "Services already running, skipping startup"
    log_pass "Using existing docker-compose environment"
  else
    compose_file="docker-compose.${ENVIRONMENT}.yml"
    if [ ! -f "$compose_file" ]; then
      compose_file="docker-compose.yml"
    fi

    log_info "Starting docker-compose environment with $compose_file..."
    if docker-compose -f "$compose_file" up -d >/dev/null 2>&1; then
      log_pass "Docker-compose environment started"
    else
      log_fail "Failed to start docker-compose environment"
      exit 1
    fi

    # Wait for Flask backend health
    log_info "Waiting for Flask backend to be healthy..."
    sleep 5  # Give services time to initialize
  fi
  log_pass "Docker-compose environment ready"
elif [ "$USE_K8S" = true ]; then
  log_info "Testing against Kubernetes cluster"
  log_info "Namespace: $NAMESPACE"

  # Verify kubectl access
  if kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
    log_pass "Kubernetes namespace '$NAMESPACE' accessible"
  else
    log_fail "Cannot access Kubernetes namespace '$NAMESPACE'"
    log_info "Make sure kubectl is configured and you have access to the cluster"
    exit 1
  fi

  # Check if deployments are running
  if kubectl -n "$NAMESPACE" get deployments 2>/dev/null | grep -q "killkrill"; then
    log_pass "KillKrill deployments found in cluster"
  else
    log_info "No KillKrill deployments found (this may be expected for new deployments)"
  fi
fi

# =============================================================================
# 1. SERVICE HEALTH CHECKS
# =============================================================================
log_section "1. SERVICE HEALTH CHECKS"

# Flask Backend health (primary service)
if http_status "$FLASK_BACKEND_URL/healthz" | grep -q "200"; then
  log_pass "Flask backend service is healthy"
else
  log_fail "Flask backend service is not responding"
fi

# Web UI health (optional - may not have /health endpoint)
web_status=$(http_status "$WEB_URL/" 2>/dev/null || echo "000")
if echo "$web_status" | grep -qE "200|304"; then
  log_pass "WebUI service is accessible"
elif echo "$web_status" | grep -q "000"; then
  log_info "WebUI service not available (may not be deployed)"
else
  log_fail "WebUI service returned unexpected status: $web_status"
fi

# Legacy API health (optional - for backwards compatibility)
api_status=$(http_status "$API_URL/health" 2>/dev/null || echo "000")
if echo "$api_status" | grep -q "200"; then
  log_pass "Legacy API service is healthy"
elif echo "$api_status" | grep -q "000"; then
  log_info "Legacy API not deployed (expected for new architecture)"
else
  log_info "Legacy API service status: $api_status"
fi

# =============================================================================
# 2. METRICS ENDPOINT
# =============================================================================
log_section "2. METRICS ENDPOINTS"

# Prometheus metrics (optional)
metrics_status=$(http_status "$FLASK_BACKEND_URL/metrics" 2>/dev/null || echo "000")
if echo "$metrics_status" | grep -q "200"; then
  log_pass "Flask backend metrics endpoint is responding"
elif echo "$metrics_status" | grep -q "000"; then
  log_info "Metrics endpoint not available (may not be enabled)"
else
  log_info "Metrics endpoint status: $metrics_status"
fi

# =============================================================================
# 3. API ENDPOINT TESTS (Legacy - Optional)
# =============================================================================
log_section "3. LEGACY API TESTS (Optional)"

# These tests are for backwards compatibility with older architecture
log_info "Skipping legacy API endpoint tests (new architecture uses Flask backend)"
log_pass "Legacy API tests skipped as expected"

# =============================================================================
# 4-7. LEGACY TESTS (Skipped)
# =============================================================================
log_section "4-7. LEGACY TESTS (Skipped)"

log_info "Skipping legacy data pipeline, license, error handling, and performance tests"
log_info "These tests are for the old architecture - new tests focus on Flask backend"
log_pass "Legacy tests skipped"

# =============================================================================
# 8. DATABASE CONNECTIVITY
# =============================================================================
log_section "8. DATABASE CONNECTIVITY"

# Check Flask backend health endpoint
if http_status "$FLASK_BACKEND_URL/healthz" | grep -q "200"; then
  log_pass "Flask backend is healthy"
else
  log_fail "Flask backend health check failed"
fi

# Test database connection through Flask backend
response=$(http_get "$FLASK_BACKEND_URL/healthz" 2>/dev/null)
if echo "$response" | jq -e '.status' | grep -q "healthy"; then
  log_pass "Database connectivity verified (Flask backend healthy)"
else
  log_fail "Database connectivity issue (Flask backend unhealthy)"
  log_info "Response: $response"
fi

# Additional database connectivity test for legacy endpoints
if [ -n "$(http_get "$API_URL/api/v1/status" 2>/dev/null)" ]; then
  log_pass "Legacy API database connectivity verified"
else
  log_info "Legacy API status endpoint not available (may be expected)"
fi

# =============================================================================
# 9. AUTHENTICATION ENDPOINTS
# =============================================================================
log_section "9. AUTHENTICATION ENDPOINTS"

# Test registration endpoint accessibility
reg_status=$(http_status "$FLASK_BACKEND_URL/api/v1/auth/register")
if echo "$reg_status" | grep -qE "200|400|409"; then
  log_pass "Registration endpoint is accessible (status: $reg_status)"
else
  log_fail "Registration endpoint failed (status: $reg_status)"
fi

# Test login endpoint accessibility (should return 400 without credentials)
login_status=$(http_status "$FLASK_BACKEND_URL/api/v1/auth/login")
if echo "$login_status" | grep -qE "200|400|401"; then
  log_pass "Login endpoint is accessible (status: $login_status)"
else
  log_fail "Login endpoint failed (status: $login_status)"
fi

# Test login with invalid credentials (should return 400 or 401)
if [ -n "$CURL_EXTRA_ARGS" ]; then
  login_response=$(eval curl -s -X POST $CURL_EXTRA_ARGS -H \"Content-Type: application/json\" \
    -d "'{\"email\": \"invalid@test.com\", \"password\": \"wrongpass\"}'" \
    -w "\"\\n%{http_code}\"" "$FLASK_BACKEND_URL/api/v1/auth/login" 2>/dev/null)
else
  login_response=$(curl -s -X POST "$FLASK_BACKEND_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email": "invalid@test.com", "password": "wrongpass"}' \
    -w "\n%{http_code}" 2>/dev/null)
fi
login_body=$(echo "$login_response" | head -n -1)
login_code=$(echo "$login_response" | tail -n 1)

if echo "$login_code" | grep -qE "400|401"; then
  log_pass "Login endpoint correctly rejects invalid credentials (status: $login_code)"
else
  log_fail "Login endpoint unexpected response (status: $login_code)"
  log_info "Response body: $login_body"
fi

# Test login with default admin credentials
if [ -n "$CURL_EXTRA_ARGS" ]; then
  admin_login_response=$(eval curl -s -X POST $CURL_EXTRA_ARGS -H \"Content-Type: application/json\" \
    -d "'{\"email\": \"admin@localhost.local\", \"password\": \"admin123\"}'" \
    -w "\"\\n%{http_code}\"" "$FLASK_BACKEND_URL/api/v1/auth/login" 2>/dev/null)
else
  admin_login_response=$(curl -s -X POST "$FLASK_BACKEND_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email": "admin@localhost.local", "password": "admin123"}' \
    -w "\n%{http_code}" 2>/dev/null)
fi
admin_login_body=$(echo "$admin_login_response" | head -n -1)
admin_login_code=$(echo "$admin_login_response" | tail -n 1)

if echo "$admin_login_code" | grep -q "200"; then
  # Verify response contains access token
  if echo "$admin_login_body" | jq -e '.data.access_token' >/dev/null 2>&1; then
    log_pass "Admin login successful with valid JWT token"

    # Extract token for further testing
    ACCESS_TOKEN=$(echo "$admin_login_body" | jq -r '.data.access_token')

    # Test authenticated endpoint with token
    if [ -n "$CURL_EXTRA_ARGS" ]; then
      me_response=$(eval curl -s -X GET $CURL_EXTRA_ARGS \
        -H \"Authorization: Bearer $ACCESS_TOKEN\" \
        -w "\"\\n%{http_code}\"" "$FLASK_BACKEND_URL/api/v1/auth/me" 2>/dev/null)
    else
      me_response=$(curl -s -X GET "$FLASK_BACKEND_URL/api/v1/auth/me" \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        -w "\n%{http_code}" 2>/dev/null)
    fi
    me_body=$(echo "$me_response" | head -n -1)
    me_code=$(echo "$me_response" | tail -n 1)

    if echo "$me_code" | grep -q "200"; then
      if echo "$me_body" | jq -e '.data.email' | grep -q "admin@localhost.local"; then
        log_pass "Authenticated /me endpoint working correctly"
      else
        log_fail "/me endpoint returned unexpected user data"
      fi
    else
      log_fail "Authenticated /me endpoint failed (status: $me_code)"
    fi
  else
    log_fail "Admin login response missing access_token"
    log_info "Response: $admin_login_body"
  fi
elif echo "$admin_login_code" | grep -qE "401|500"; then
  log_fail "Admin login failed (status: $admin_login_code) - database or seed issue?"
  log_info "Response: $admin_login_body"
  log_info "Check if admin user was seeded correctly"
else
  log_fail "Admin login unexpected status: $admin_login_code"
  log_info "Response: $admin_login_body"
fi

# Test token refresh endpoint accessibility
refresh_status=$(http_status "$FLASK_BACKEND_URL/api/v1/auth/refresh")
if echo "$refresh_status" | grep -qE "200|400|401"; then
  log_pass "Token refresh endpoint is accessible (status: $refresh_status)"
else
  log_fail "Token refresh endpoint failed (status: $refresh_status)"
fi

# =============================================================================
# CLEANUP
# =============================================================================
# Only cleanup for docker-compose environments, NOT for K8s
if [ "$USE_COMPOSE" = true ]; then
  log_section "CLEANUP"
  log_info "Note: Skipping cleanup to preserve environment for development"
  log_info "To manually clean up, run: docker-compose down -v"
  log_pass "Environment preserved for continued testing"
elif [ "$USE_K8S" = true ]; then
  log_section "CLEANUP"
  log_info "Kubernetes environment - no cleanup needed"
  log_pass "K8s cluster remains running"
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
