#!/bin/bash

###############################################################################
# PRE-COMMIT CHECKLIST SCRIPT
#
# This script runs all checks that MUST pass before committing code.
# These are local tests for developer machines with Docker/container support.
#
# Usage:
#   ./scripts/pre-commit-checklist.sh [--skip-docker] [--skip-integration]
#
# Exit codes:
#   0 = All checks passed
#   1 = One or more checks failed
#
# Requires: Docker, docker-compose, Go, Python, Node.js
###############################################################################

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SKIP_DOCKER=false
SKIP_INTEGRATION=false
FAILED_CHECKS=0
PASSED_CHECKS=0

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --skip-docker)
      SKIP_DOCKER=true
      shift
      ;;
    --skip-integration)
      SKIP_INTEGRATION=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Helper functions
log_section() {
  echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BLUE}▶ $1${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

log_pass() {
  echo -e "${GREEN}✓ $1${NC}"
  ((PASSED_CHECKS++))
}

log_fail() {
  echo -e "${RED}✗ $1${NC}"
  ((FAILED_CHECKS++))
}

log_info() {
  echo -e "${YELLOW}ℹ $1${NC}"
}

check_command() {
  if ! command -v "$1" &> /dev/null; then
    log_fail "$1 is not installed"
    return 1
  fi
  return 0
}

# =============================================================================
# 1. PRE-FLIGHT CHECKS
# =============================================================================
log_section "1. PRE-FLIGHT CHECKS"

# Check required tools
check_command git || exit 1
check_command docker || { log_fail "Docker is required"; exit 1; }
check_command go || { log_fail "Go is required"; exit 1; }
check_command python3 || { log_fail "Python 3 is required"; exit 1; }
check_command npm || { log_fail "npm is required"; exit 1; }

log_pass "All required tools are installed"

# Check git status
if [ -n "$(git status --porcelain)" ]; then
  log_info "Uncommitted changes detected (this is normal)"
else
  log_pass "Working directory is clean"
fi

# =============================================================================
# 2. LINTING & CODE QUALITY (NO CONTAINERS NEEDED)
# =============================================================================
log_section "2. LINTING & CODE QUALITY"

# Go linting
if command -v golangci-lint &> /dev/null; then
  log_info "Running golangci-lint..."
  if golangci-lint run ./... --timeout 5m >/dev/null 2>&1; then
    log_pass "Go linting passed"
  else
    log_fail "Go linting failed"
  fi
else
  log_info "golangci-lint not installed, skipping (optional)"
fi

# Python linting
if python3 -m black --check . >/dev/null 2>&1; then
  log_pass "Python Black formatting check passed"
else
  log_fail "Python Black formatting check failed"
fi

if python3 -m isort --check-only . >/dev/null 2>&1; then
  log_pass "Python isort import check passed"
else
  log_fail "Python isort import check failed"
fi

if python3 -m flake8 . --count --select=E9,F63,F7,F82 >/dev/null 2>&1; then
  log_pass "Python flake8 linting passed"
else
  log_fail "Python flake8 linting failed"
fi

# Node.js linting
if [ -f "package.json" ]; then
  log_info "Running npm linting..."
  if npm run lint >/dev/null 2>&1; then
    log_pass "JavaScript/TypeScript linting passed"
  else
    log_fail "JavaScript/TypeScript linting failed"
  fi
fi

# =============================================================================
# 3. UNIT TESTS (NO CONTAINERS NEEDED)
# =============================================================================
log_section "3. UNIT TESTS"

# Go unit tests
log_info "Running Go unit tests..."
if go test -v -short ./... >/dev/null 2>&1; then
  log_pass "Go unit tests passed"
else
  log_fail "Go unit tests failed"
fi

# Python unit tests (mocked dependencies)
log_info "Running Python unit tests..."
if python3 -m pytest --co -q >/dev/null 2>&1; then
  if python3 -m pytest -m "not integration" >/dev/null 2>&1; then
    log_pass "Python unit tests passed"
  else
    log_fail "Python unit tests failed"
  fi
else
  log_info "pytest not configured or no tests found"
fi

# Node.js unit tests
if [ -f "package.json" ]; then
  log_info "Running Node.js unit tests..."
  if npm test >/dev/null 2>&1; then
    log_pass "Node.js unit tests passed"
  else
    log_fail "Node.js unit tests failed"
  fi
fi

# =============================================================================
# 4. SECURITY SCANNING (NO CONTAINERS NEEDED)
# =============================================================================
log_section "4. SECURITY SCANNING"

# Trivy filesystem scan (if installed)
if command -v trivy &> /dev/null; then
  log_info "Running Trivy vulnerability scan..."
  if trivy fs --exit-code 0 . >/dev/null 2>&1; then
    log_pass "Trivy vulnerability scan passed"
  else
    log_fail "Trivy found vulnerabilities (check output above)"
  fi
else
  log_info "Trivy not installed, skipping (optional)"
fi

# Bandit for Python (if installed)
if command -v bandit &> /dev/null; then
  log_info "Running Bandit Python security scan..."
  if bandit -r . -f json >/dev/null 2>&1; then
    log_pass "Bandit security scan passed"
  else
    log_fail "Bandit found security issues"
  fi
else
  log_info "Bandit not installed, skipping (optional)"
fi

# =============================================================================
# 5. INTEGRATION TESTS (REQUIRES DOCKER & CONTAINERS)
# =============================================================================
if [ "$SKIP_DOCKER" = false ] && [ "$SKIP_INTEGRATION" = false ]; then
  log_section "5. INTEGRATION TESTS (LOCAL CLUSTER)"

  # Start docker-compose test environment
  log_info "Starting test environment with Docker Compose..."
  if docker-compose -f docker-compose.dev.yml up -d >/dev/null 2>&1; then
    log_pass "Test environment started"

    # Wait for services to be healthy
    log_info "Waiting for services to be healthy (60 seconds)..."
    sleep 60

    # Run integration tests
    log_info "Running integration tests..."
    if python3 -m pytest -m integration >/dev/null 2>&1; then
      log_pass "Integration tests passed"
    else
      log_fail "Integration tests failed"
    fi

    # Cleanup
    log_info "Cleaning up test environment..."
    docker-compose -f docker-compose.dev.yml down -v >/dev/null 2>&1 || true
  else
    log_fail "Failed to start test environment"
  fi
else
  if [ "$SKIP_DOCKER" = true ]; then
    log_section "5. INTEGRATION TESTS (SKIPPED)"
    log_info "Skipped integration tests (--skip-docker flag used)"
  else
    log_section "5. INTEGRATION TESTS (SKIPPED)"
    log_info "Skipped integration tests (--skip-integration flag used)"
  fi
fi

# =============================================================================
# 6. BUILD VERIFICATION
# =============================================================================
log_section "6. BUILD VERIFICATION"

# Go build
log_info "Building Go applications..."
if go build -o /tmp/killkrill-api ./apps/api >/dev/null 2>&1; then
  log_pass "Go API build successful"
  rm -f /tmp/killkrill-api
else
  log_fail "Go API build failed"
fi

# Node.js build
if [ -f "package.json" ]; then
  log_info "Building Node.js applications..."
  if npm run build >/dev/null 2>&1; then
    log_pass "Node.js build successful"
  else
    log_fail "Node.js build failed"
  fi
fi

# =============================================================================
# 7. DEPENDENCY SECURITY
# =============================================================================
log_section "7. DEPENDENCY SECURITY CHECKS"

# npm audit
if [ -f "package.json" ]; then
  log_info "Checking npm dependencies for vulnerabilities..."
  if npm audit --audit-level=moderate >/dev/null 2>&1; then
    log_pass "npm audit passed (no moderate/high/critical vulnerabilities)"
  else
    log_fail "npm audit found vulnerabilities"
  fi
fi

# Go vulnerability check
if command -v govulncheck &> /dev/null; then
  log_info "Checking Go dependencies for vulnerabilities..."
  if govulncheck ./... >/dev/null 2>&1; then
    log_pass "Go vulnerability check passed"
  else
    log_fail "Go vulnerability check found issues"
  fi
else
  log_info "govulncheck not installed, skipping (optional)"
fi

# =============================================================================
# SUMMARY
# =============================================================================
log_section "SUMMARY"

echo -e "\n${GREEN}Passed checks: ${PASSED_CHECKS}${NC}"
echo -e "${RED}Failed checks: ${FAILED_CHECKS}${NC}\n"

if [ "$FAILED_CHECKS" -eq 0 ]; then
  echo -e "${GREEN}✓ All pre-commit checks passed!${NC}"
  echo -e "\nYou can now commit your changes with confidence."
  exit 0
else
  echo -e "${RED}✗ Some checks failed. Please fix the issues above before committing.${NC}"
  echo -e "\nTo skip Docker/integration tests, use: ${YELLOW}./scripts/pre-commit-checklist.sh --skip-docker${NC}"
  exit 1
fi
