#!/bin/bash
# KillKrill Flask Backend Startup Script
# Runs both Flask HTTP server and gRPC server in parallel

set -e

# Configuration
FLASK_HOST="${FLASK_HOST:-0.0.0.0}"
FLASK_PORT="${FLASK_PORT:-5000}"
GRPC_PORT="${GRPC_PORT:-50051}"
WORKERS="${WORKERS:-0}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

# Auto-calculate workers if not specified
if [ "$WORKERS" = "0" ]; then
    WORKERS=$(nproc)
fi

# Log startup
echo "Starting KillKrill Flask Backend"
echo "  Flask HTTP: $FLASK_HOST:$FLASK_PORT"
echo "  gRPC Server: $GRPC_PORT"
echo "  Workers: $WORKERS"
echo "  Log Level: $LOG_LEVEL"

# Run application with both Flask and gRPC
exec python3 /app/main.py \
    --host "$FLASK_HOST" \
    --port "$FLASK_PORT" \
    --grpc-port "$GRPC_PORT" \
    --workers "$WORKERS" \
    --env production
