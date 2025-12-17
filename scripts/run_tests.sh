#!/bin/bash

# Killkrill comprehensive test runner
# Runs unit, API, integration, and load tests with configurable options

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_DIR="${PROJECT_ROOT}/tests"
REPORTS_DIR="/tmp/killkrill-tests"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Default options
RUN_UNIT=true
RUN_API=true
RUN_INTEGRATION=true
RUN_LOAD=false
COVERAGE=true
VERBOSE=false
PARALLEL=true
JUNIT_OUTPUT=true

# Usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    -u, --unit           Run unit tests only
    -a, --api            Run API tests only
    -i, --integration    Run integration tests only
    -l, --load           Run load tests only
    -f, --full           Run all test suites (default: excludes load tests)
    -c, --no-coverage    Disable coverage reporting
    -v, --verbose        Verbose output
    -s, --serial         Run tests serially (default: parallel)
    -j, --no-junit       Disable JUnit XML output
    -h, --help           Show this help message

Examples:
    $0                   # Run unit, API, and integration tests
    $0 --unit --api      # Run only unit and API tests
    $0 --full            # Run all test suites including load tests
    $0 --unit -v         # Run unit tests with verbose output

EOF
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--unit)
            RUN_UNIT=true
            RUN_API=false
            RUN_INTEGRATION=false
            shift
            ;;
        -a|--api)
            RUN_UNIT=false
            RUN_API=true
            RUN_INTEGRATION=false
            shift
            ;;
        -i|--integration)
            RUN_UNIT=false
            RUN_API=false
            RUN_INTEGRATION=true
            shift
            ;;
        -l|--load)
            RUN_LOAD=true
            shift
            ;;
        -f|--full)
            RUN_UNIT=true
            RUN_API=true
            RUN_INTEGRATION=true
            RUN_LOAD=true
            shift
            ;;
        -c|--no-coverage)
            COVERAGE=false
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -s|--serial)
            PARALLEL=false
            shift
            ;;
        -j|--no-junit)
            JUNIT_OUTPUT=false
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# Setup
mkdir -p "${REPORTS_DIR}"
cd "${PROJECT_ROOT}"

# Build pytest arguments
PYTEST_ARGS="-v"
PYTEST_ARGS="${PYTEST_ARGS} --tb=short"

if [ "${VERBOSE}" = true ]; then
    PYTEST_ARGS="${PYTEST_ARGS} -vv"
fi

if [ "${COVERAGE}" = true ]; then
    PYTEST_ARGS="${PYTEST_ARGS} --cov=services --cov=tests --cov-report=html:${REPORTS_DIR}/coverage --cov-report=term-missing --cov-report=xml:${REPORTS_DIR}/coverage.xml"
fi

if [ "${JUNIT_OUTPUT}" = true ]; then
    PYTEST_ARGS="${PYTEST_ARGS} --junitxml=${REPORTS_DIR}/junit-${TIMESTAMP}.xml"
fi

if [ "${PARALLEL}" = true ]; then
    PYTEST_ARGS="${PYTEST_ARGS} -n auto"
fi

# Print configuration
echo -e "${BLUE}=== Killkrill Test Suite ===${NC}"
echo -e "${BLUE}Timestamp: ${TIMESTAMP}${NC}"
echo -e "${BLUE}Project Root: ${PROJECT_ROOT}${NC}"
echo -e "${BLUE}Test Directory: ${TEST_DIR}${NC}"
echo ""
echo -e "Configuration:"
echo "  Unit Tests:        ${RUN_UNIT}"
echo "  API Tests:         ${RUN_API}"
echo "  Integration Tests: ${RUN_INTEGRATION}"
echo "  Load Tests:        ${RUN_LOAD}"
echo "  Coverage:          ${COVERAGE}"
echo "  Parallel:          ${PARALLEL}"
echo "  Verbose:           ${VERBOSE}"
echo ""

# Run tests
test_failed=0
total_tests=0

if [ "${RUN_UNIT}" = true ]; then
    echo -e "${YELLOW}Running unit tests...${NC}"
    if pytest ${PYTEST_ARGS} -m unit "${TEST_DIR}/unit" 2>&1 | tee -a "${REPORTS_DIR}/test-output-${TIMESTAMP}.log"; then
        echo -e "${GREEN}✓ Unit tests passed${NC}"
        ((total_tests++))
    else
        echo -e "${RED}✗ Unit tests failed${NC}"
        test_failed=1
    fi
    echo ""
fi

if [ "${RUN_API}" = true ]; then
    echo -e "${YELLOW}Running API tests...${NC}"
    if pytest ${PYTEST_ARGS} -m api "${TEST_DIR}/api" 2>&1 | tee -a "${REPORTS_DIR}/test-output-${TIMESTAMP}.log"; then
        echo -e "${GREEN}✓ API tests passed${NC}"
        ((total_tests++))
    else
        echo -e "${RED}✗ API tests failed${NC}"
        test_failed=1
    fi
    echo ""
fi

if [ "${RUN_INTEGRATION}" = true ]; then
    echo -e "${YELLOW}Running integration tests...${NC}"
    if pytest ${PYTEST_ARGS} -m integration "${TEST_DIR}/integration" 2>&1 | tee -a "${REPORTS_DIR}/test-output-${TIMESTAMP}.log"; then
        echo -e "${GREEN}✓ Integration tests passed${NC}"
        ((total_tests++))
    else
        echo -e "${RED}✗ Integration tests failed${NC}"
        test_failed=1
    fi
    echo ""
fi

if [ "${RUN_LOAD}" = true ]; then
    echo -e "${YELLOW}Running load tests...${NC}"
    if pytest ${PYTEST_ARGS} -m load "${TEST_DIR}/load" 2>&1 | tee -a "${REPORTS_DIR}/test-output-${TIMESTAMP}.log"; then
        echo -e "${GREEN}✓ Load tests passed${NC}"
        ((total_tests++))
    else
        echo -e "${RED}✗ Load tests failed${NC}"
        test_failed=1
    fi
    echo ""
fi

# Summary
echo -e "${BLUE}=== Test Summary ===${NC}"
echo "Tests run: ${total_tests}"
echo "Reports directory: ${REPORTS_DIR}"

if [ "${COVERAGE}" = true ]; then
    echo "Coverage report: ${REPORTS_DIR}/coverage/index.html"
fi

if [ "${test_failed}" -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
fi
