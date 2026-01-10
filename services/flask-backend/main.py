#!/usr/bin/env python3
"""
KillKrill Flask Backend - Application Entry Point

Production-ready entry point for the Flask backend service.
Supports running as HTTP server, gRPC server, or both in separate processes.

Environment Variables:
    FLASK_ENV: development|testing|production (default: development)
    FLASK_PORT: HTTP server port (default: 5000)
    GRPC_PORT: gRPC server port (default: 50051)
    RUN_GRPC: true|false - whether to run gRPC server (default: true)
    WORKERS: Number of Gunicorn workers (default: 4, auto if 0)
    DATABASE_URL: PostgreSQL/MySQL connection string
    JWT_SECRET: JWT signing secret
    LOG_LEVEL: DEBUG|INFO|WARNING|ERROR|CRITICAL (default: INFO)
"""

import argparse
import logging
import os
import sys
from typing import Optional

import structlog
from decouple import config

# Configure logging before importing app
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


def run_http_server(
    app, host: str = "0.0.0.0", port: int = 5000, workers: int = 4
) -> None:
    """Run Flask HTTP server with Gunicorn"""
    try:
        import gunicorn.app.wsgiapp
        from gunicorn.arbiter import Arbiter
        from gunicorn.config import Config

        logger.info("starting_http_server", host=host, port=port, workers=workers)

        sys.argv = [
            "gunicorn",
            f"--bind={host}:{port}",
            f"--workers={workers}",
            "--worker-class=sync",
            "--timeout=30",
            "--access-logfile=-",
            "--error-logfile=-",
            "main:app",
        ]

        # Run Gunicorn
        app.run(host=host, port=port, debug=False)

    except Exception as e:
        logger.error("http_server_error", error=str(e), error_type=type(e).__name__)
        raise


def run_grpc_server(port: int = 50051) -> None:
    """Run gRPC server on separate port"""
    try:
        from concurrent import futures

        import grpc

        logger.info("starting_grpc_server", port=port)

        # Create gRPC server
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

        # Add gRPC service implementations here
        # Example: add_ExampleServicer_to_server(ExampleServicer(), server)

        server.add_insecure_port(f"[::]:{port}")
        server.start()

        logger.info("grpc_server_started", port=port)

        # Keep server running
        server.wait_for_termination()

    except Exception as e:
        logger.error("grpc_server_error", error=str(e), error_type=type(e).__name__)
        raise


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="KillKrill Flask Backend")
    parser.add_argument(
        "--env",
        choices=["development", "testing", "production"],
        default=config("FLASK_ENV", default="development"),
        help="Execution environment",
    )
    parser.add_argument(
        "--host",
        default=config("FLASK_HOST", default="0.0.0.0"),
        help="HTTP server host",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=config("FLASK_PORT", default=5000, cast=int),
        help="HTTP server port",
    )
    parser.add_argument(
        "--grpc-port",
        type=int,
        default=config("GRPC_PORT", default=50051, cast=int),
        help="gRPC server port",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=config("WORKERS", default=4, cast=int),
        help="Number of Gunicorn workers (0 = auto)",
    )
    parser.add_argument("--no-grpc", action="store_true", help="Disable gRPC server")
    parser.add_argument(
        "--grpc-only", action="store_true", help="Run gRPC server only (no HTTP)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    # Set environment
    os.environ["FLASK_ENV"] = args.env

    # Import Flask app factory
    from app import create_app

    # Create Flask app
    app = create_app(env=args.env)

    # Set debug mode
    if args.debug or args.env == "development":
        app.debug = True

    # Calculate workers
    if args.workers == 0:
        import multiprocessing

        workers = multiprocessing.cpu_count()
    else:
        workers = args.workers

    logger.info(
        "application_starting",
        environment=args.env,
        host=args.host,
        port=args.port,
        grpc_port=args.grpc_port,
        workers=workers,
        debug=app.debug,
    )

    try:
        if args.grpc_only:
            # Run gRPC server only
            run_grpc_server(port=args.grpc_port)
        elif args.no_grpc:
            # Run HTTP server only
            run_http_server(app, host=args.host, port=args.port, workers=workers)
        else:
            # Run both HTTP and gRPC servers
            import multiprocessing

            http_process = multiprocessing.Process(
                target=run_http_server,
                args=(app, args.host, args.port, workers),
                name="HTTP-Server",
            )
            grpc_process = multiprocessing.Process(
                target=run_grpc_server, args=(args.grpc_port,), name="gRPC-Server"
            )

            http_process.start()
            grpc_process.start()

            logger.info(
                "services_started", http_pid=http_process.pid, grpc_pid=grpc_process.pid
            )

            # Wait for processes
            http_process.join()
            grpc_process.join()

    except KeyboardInterrupt:
        logger.info("application_stopped_by_user")
    except Exception as e:
        logger.error("application_error", error=str(e), error_type=type(e).__name__)
        sys.exit(1)


if __name__ == "__main__":
    main()
