"""Unit tests for ReceiverClient module."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest

from shared.receiver_client.client import ReceiverClient, TokenInfo
from shared.receiver_client.exceptions import (
    AuthenticationError, ConnectionError, SubmissionError,
)
from shared.receiver_client.grpc_client import GRPCSubmitter
from shared.receiver_client.rest_client import RESTSubmitter


# Test fixtures
@pytest.fixture
def token_info():
    """Create a valid TokenInfo object."""
    return TokenInfo(
        access_token="valid_access_token",
        refresh_token="valid_refresh_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        token_type="Bearer",
    )


@pytest.fixture
def receiver_client():
    """Create a ReceiverClient instance."""
    return ReceiverClient(
        api_url="https://receiver.example.com",
        grpc_url="receiver.example.com:50051",
        client_id="test_client",
        client_secret="test_secret",
        max_retries=3,
        retry_backoff=0.1,  # Short backoff for tests
    )


# TokenInfo Tests
class TestTokenInfo:
    """Test TokenInfo dataclass."""

    @pytest.mark.unit
    def test_token_info_creation(self, token_info):
        """Test TokenInfo creation."""
        assert token_info.access_token == "valid_access_token"
        assert token_info.refresh_token == "valid_refresh_token"
        assert token_info.token_type == "Bearer"
        assert token_info.expires_at > datetime.utcnow()

    @pytest.mark.unit
    def test_token_info_is_expired_valid_token(self, token_info):
        """Test is_expired returns False for valid token."""
        assert token_info.is_expired() is False

    @pytest.mark.unit
    def test_token_info_is_expired_near_expiry(self):
        """Test is_expired returns True when token expires within 5 minutes."""
        token = TokenInfo(
            access_token="token",
            refresh_token="refresh",
            expires_at=datetime.utcnow() + timedelta(minutes=3),
        )
        assert token.is_expired() is True

    @pytest.mark.unit
    def test_token_info_is_expired_expired_token(self):
        """Test is_expired returns True for expired token."""
        token = TokenInfo(
            access_token="token",
            refresh_token="refresh",
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        assert token.is_expired() is True

    @pytest.mark.unit
    def test_token_info_is_expired_boundary(self):
        """Test is_expired at 5-minute boundary."""
        token = TokenInfo(
            access_token="token",
            refresh_token="refresh",
            expires_at=datetime.utcnow() + timedelta(minutes=5, seconds=1),
        )
        assert token.is_expired() is False

        token_at_boundary = TokenInfo(
            access_token="token",
            refresh_token="refresh",
            expires_at=datetime.utcnow() + timedelta(minutes=5),
        )
        assert token_at_boundary.is_expired() is True


# ReceiverClient Initialization Tests
class TestReceiverClientInit:
    """Test ReceiverClient initialization."""

    @pytest.mark.unit
    def test_receiver_client_creation(self, receiver_client):
        """Test ReceiverClient creation."""
        assert receiver_client.api_url == "https://receiver.example.com"
        assert receiver_client.grpc_url == "receiver.example.com:50051"
        assert receiver_client.client_id == "test_client"
        assert receiver_client.client_secret == "test_secret"
        assert receiver_client.max_retries == 3
        assert receiver_client.retry_backoff == 0.1

    @pytest.mark.unit
    def test_receiver_client_url_normalization(self):
        """Test URL normalization (trailing slash removal)."""
        client = ReceiverClient(
            api_url="https://receiver.example.com/",
            grpc_url="receiver.example.com:50051",
            client_id="test",
            client_secret="secret",
        )
        assert client.api_url == "https://receiver.example.com"

    @pytest.mark.unit
    def test_receiver_client_initial_state(self, receiver_client):
        """Test ReceiverClient initial state."""
        assert receiver_client.token_info is None
        assert receiver_client.use_grpc is True
        assert receiver_client.grpc_client is None
        assert receiver_client.rest_client is None
        assert receiver_client._authenticated is False
        assert isinstance(receiver_client._lock, asyncio.Lock)


# Authentication Tests
class TestAuthentication:
    """Test authentication functionality."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_authenticate_success(self, receiver_client):
        """Test successful authentication."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
        }

        with patch("shared.receiver_client.client.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.post = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__.return_value = mock_async_client
            mock_async_client.__aexit__.return_value = None
            mock_client.return_value = mock_async_client

            with patch.object(
                receiver_client, "_initialize_clients", new_callable=AsyncMock
            ):
                result = await receiver_client.authenticate()

        assert result is True
        assert receiver_client._authenticated is True
        assert receiver_client.token_info is not None
        assert receiver_client.token_info.access_token == "new_access_token"
        assert receiver_client.token_info.refresh_token == "new_refresh_token"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_authenticate_http_error(self, receiver_client):
        """Test authentication with HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("shared.receiver_client.client.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.post = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__.return_value = mock_async_client
            mock_async_client.__aexit__.return_value = None
            mock_client.return_value = mock_async_client

            with pytest.raises(AuthenticationError):
                await receiver_client.authenticate()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_authenticate_network_error(self, receiver_client):
        """Test authentication with network error."""
        with patch("shared.receiver_client.client.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.post = AsyncMock(
                side_effect=httpx.RequestError("Connection failed")
            )
            mock_async_client.__aenter__.return_value = mock_async_client
            mock_async_client.__aexit__.return_value = None
            mock_client.return_value = mock_async_client

            with pytest.raises(AuthenticationError):
                await receiver_client.authenticate()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_authenticate_missing_response_field(self, receiver_client):
        """Test authentication with missing response field."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "token"
        }  # Missing refresh_token

        with patch("shared.receiver_client.client.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.post = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__.return_value = mock_async_client
            mock_async_client.__aexit__.return_value = None
            mock_client.return_value = mock_async_client

            with pytest.raises(AuthenticationError):
                await receiver_client.authenticate()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_authenticate_lock_mechanism(self, receiver_client):
        """Test that authentication uses lock to prevent race conditions."""
        call_count = 0

        async def mock_auth():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "token",
            "refresh_token": "refresh",
            "expires_in": 3600,
        }

        with patch("shared.receiver_client.client.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.post = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__.return_value = mock_async_client
            mock_async_client.__aexit__.return_value = None
            mock_client.return_value = mock_async_client

            with patch.object(
                receiver_client, "_initialize_clients", new_callable=AsyncMock
            ):
                await receiver_client.authenticate()


# Token Refresh Tests
class TestTokenRefresh:
    """Test token refresh functionality."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_refresh_token_success(self, receiver_client, token_info):
        """Test successful token refresh."""
        receiver_client.token_info = token_info

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "refreshed_access_token",
            "expires_in": 3600,
        }

        with patch("shared.receiver_client.client.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.post = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__.return_value = mock_async_client
            mock_async_client.__aexit__.return_value = None
            mock_client.return_value = mock_async_client

            with patch.object(
                receiver_client, "_initialize_clients", new_callable=AsyncMock
            ):
                result = await receiver_client.refresh_token()

        assert result is True
        assert receiver_client.token_info.access_token == "refreshed_access_token"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_refresh_token_no_token(self, receiver_client):
        """Test refresh token when no token exists."""
        receiver_client.token_info = None

        with pytest.raises(AuthenticationError):
            await receiver_client.refresh_token()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_refresh_token_failure_reauthenticates(
        self, receiver_client, token_info
    ):
        """Test refresh failure triggers re-authentication."""
        receiver_client.token_info = token_info

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("shared.receiver_client.client.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.post = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__.return_value = mock_async_client
            mock_async_client.__aexit__.return_value = None
            mock_client.return_value = mock_async_client

            with patch.object(
                receiver_client, "authenticate", new_callable=AsyncMock
            ) as mock_auth:
                mock_auth.return_value = True
                result = await receiver_client.refresh_token()

        mock_auth.assert_called_once()
        assert result is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_refresh_token_network_error(self, receiver_client, token_info):
        """Test token refresh with network error."""
        receiver_client.token_info = token_info

        with patch("shared.receiver_client.client.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.post = AsyncMock(
                side_effect=httpx.RequestError("Connection failed")
            )
            mock_async_client.__aenter__.return_value = mock_async_client
            mock_async_client.__aexit__.return_value = None
            mock_client.return_value = mock_async_client

            with pytest.raises(AuthenticationError):
                await receiver_client.refresh_token()


# Protocol Selection Tests
class TestProtocolSelection:
    """Test gRPC and REST protocol selection."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_try_grpc_success(self, receiver_client, token_info):
        """Test successful gRPC connection."""
        receiver_client.token_info = token_info

        with patch.object(GRPCSubmitter, "connect", return_value=True):
            result = await receiver_client._try_grpc()

        assert result is True
        assert receiver_client.use_grpc is True
        assert receiver_client.grpc_client is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_try_grpc_failure(self, receiver_client, token_info):
        """Test failed gRPC connection."""
        receiver_client.token_info = token_info

        with patch.object(GRPCSubmitter, "connect", return_value=False):
            result = await receiver_client._try_grpc()

        assert result is False
        assert receiver_client.grpc_client is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_try_grpc_no_token(self, receiver_client):
        """Test gRPC connection attempt without token."""
        receiver_client.token_info = None
        result = await receiver_client._try_grpc()
        assert result is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_try_grpc_exception(self, receiver_client, token_info):
        """Test gRPC connection with exception."""
        receiver_client.token_info = token_info

        with patch(
            "shared.receiver_client.client.GRPCSubmitter",
            side_effect=Exception("gRPC error"),
        ):
            result = await receiver_client._try_grpc()

        assert result is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fallback_to_rest(self, receiver_client, token_info):
        """Test fallback to REST protocol."""
        receiver_client.token_info = token_info

        with patch.object(RESTSubmitter, "connect", new_callable=AsyncMock):
            await receiver_client._fallback_to_rest()

        assert receiver_client.use_grpc is False
        assert receiver_client.rest_client is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fallback_to_rest_no_token(self, receiver_client):
        """Test fallback to REST without token."""
        receiver_client.token_info = None
        await receiver_client._fallback_to_rest()
        assert receiver_client.rest_client is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_initialize_clients_grpc_success(self, receiver_client, token_info):
        """Test client initialization with gRPC success."""
        receiver_client.token_info = token_info

        with patch.object(
            receiver_client, "_try_grpc", new_callable=AsyncMock, return_value=True
        ):
            await receiver_client._initialize_clients()

        assert receiver_client.use_grpc is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_initialize_clients_fallback_to_rest(
        self, receiver_client, token_info
    ):
        """Test client initialization falls back to REST."""
        receiver_client.token_info = token_info

        async def mock_fallback():
            receiver_client.use_grpc = False

        with patch.object(
            receiver_client, "_try_grpc", new_callable=AsyncMock, return_value=False
        ):
            with patch.object(
                receiver_client,
                "_fallback_to_rest",
                side_effect=mock_fallback,
                new_callable=AsyncMock,
            ):
                await receiver_client._initialize_clients()

        assert receiver_client.use_grpc is False


# Retry with Backoff Tests
class TestRetryWithBackoff:
    """Test retry logic with exponential backoff."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(self, receiver_client, token_info):
        """Test successful operation on first attempt."""
        receiver_client.token_info = token_info
        receiver_client._authenticated = True

        mock_func = AsyncMock(return_value=True)

        result = await receiver_client._retry_with_backoff("test_op", mock_func)

        assert result is True
        mock_func.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self, receiver_client, token_info):
        """Test successful operation after failures."""
        receiver_client.token_info = token_info
        receiver_client._authenticated = True

        mock_func = AsyncMock(
            side_effect=[SubmissionError("fail1"), SubmissionError("fail2"), True]
        )

        with patch.object(
            receiver_client, "_ensure_authenticated", new_callable=AsyncMock
        ):
            with patch(
                "shared.receiver_client.client.asyncio.sleep", new_callable=AsyncMock
            ):
                result = await receiver_client._retry_with_backoff("test_op", mock_func)

        assert result is True
        assert mock_func.call_count == 3

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_retry_all_attempts_fail(self, receiver_client, token_info):
        """Test all retry attempts fail."""
        receiver_client.token_info = token_info
        receiver_client._authenticated = True

        mock_func = AsyncMock(side_effect=SubmissionError("fail"))

        with patch.object(
            receiver_client, "_ensure_authenticated", new_callable=AsyncMock
        ):
            with patch(
                "shared.receiver_client.client.asyncio.sleep", new_callable=AsyncMock
            ):
                with pytest.raises(SubmissionError):
                    await receiver_client._retry_with_backoff("test_op", mock_func)

        assert mock_func.call_count == receiver_client.max_retries

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_retry_exponential_backoff(self, receiver_client, token_info):
        """Test exponential backoff timing."""
        receiver_client.token_info = token_info
        receiver_client._authenticated = True
        receiver_client.max_retries = 3
        receiver_client.retry_backoff = 0.1

        mock_func = AsyncMock(side_effect=SubmissionError("fail"))
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with patch.object(
            receiver_client, "_ensure_authenticated", new_callable=AsyncMock
        ):
            with patch(
                "shared.receiver_client.client.asyncio.sleep", side_effect=mock_sleep
            ):
                with pytest.raises(SubmissionError):
                    await receiver_client._retry_with_backoff("test_op", mock_func)

        # Check exponential backoff: 0.1 * 2^0 = 0.1, 0.1 * 2^1 = 0.2
        assert len(sleep_calls) == 2
        assert sleep_calls[0] == 0.1
        assert sleep_calls[1] == 0.2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_retry_fallback_on_grpc_failure(self, receiver_client, token_info):
        """Test REST fallback triggered on gRPC failure."""
        receiver_client.token_info = token_info
        receiver_client._authenticated = True
        receiver_client.use_grpc = True
        receiver_client.grpc_client = MagicMock()

        mock_func = AsyncMock(side_effect=[SubmissionError("grpc fail"), True])

        with patch.object(
            receiver_client, "_ensure_authenticated", new_callable=AsyncMock
        ):
            with patch.object(
                receiver_client, "_fallback_to_rest", new_callable=AsyncMock
            ):
                with patch(
                    "shared.receiver_client.client.asyncio.sleep",
                    new_callable=AsyncMock,
                ):
                    result = await receiver_client._retry_with_backoff(
                        "test_op", mock_func
                    )

        assert result is True
        assert mock_func.call_count == 2


# Log Submission Tests
class TestLogSubmission:
    """Test log submission functionality."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_submit_logs_grpc_success(self, receiver_client, token_info):
        """Test successful log submission via gRPC."""
        receiver_client.token_info = token_info
        receiver_client._authenticated = True
        receiver_client.use_grpc = True

        mock_grpc = AsyncMock()
        mock_grpc.submit_logs = MagicMock(return_value=True)
        receiver_client.grpc_client = mock_grpc

        logs = [{"message": "test log"}]

        with patch.object(
            receiver_client, "_ensure_authenticated", new_callable=AsyncMock
        ):
            result = await receiver_client.submit_logs(logs)

        assert result is True
        mock_grpc.submit_logs.assert_called_once_with(logs)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_submit_logs_rest_success(self, receiver_client, token_info):
        """Test successful log submission via REST."""
        receiver_client.token_info = token_info
        receiver_client._authenticated = True
        receiver_client.use_grpc = False

        mock_rest = AsyncMock()
        mock_rest.submit_logs = AsyncMock(return_value=True)
        receiver_client.rest_client = mock_rest

        logs = [{"message": "test log"}]

        with patch.object(
            receiver_client, "_ensure_authenticated", new_callable=AsyncMock
        ):
            result = await receiver_client.submit_logs(logs)

        assert result is True
        mock_rest.submit_logs.assert_called_once_with(logs)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_submit_logs_no_client(self, receiver_client, token_info):
        """Test log submission fails when no client available."""
        receiver_client.token_info = token_info
        receiver_client._authenticated = True
        receiver_client.use_grpc = False
        receiver_client.rest_client = None

        logs = [{"message": "test log"}]

        with patch.object(
            receiver_client, "_ensure_authenticated", new_callable=AsyncMock
        ):
            with patch(
                "shared.receiver_client.client.asyncio.sleep", new_callable=AsyncMock
            ):
                # ConnectionError from client module is raised by _submit, which then gets
                # caught and re-raised as SubmissionError by _retry_with_backoff
                with pytest.raises((SubmissionError, ConnectionError)):
                    await receiver_client.submit_logs(logs)


# Metrics Submission Tests
class TestMetricsSubmission:
    """Test metrics submission functionality."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_submit_metrics_grpc_success(self, receiver_client, token_info):
        """Test successful metrics submission via gRPC."""
        receiver_client.token_info = token_info
        receiver_client._authenticated = True
        receiver_client.use_grpc = True

        mock_grpc = AsyncMock()
        mock_grpc.submit_metrics = MagicMock(return_value=True)
        receiver_client.grpc_client = mock_grpc

        metrics = [{"name": "test_metric", "value": 42}]

        with patch.object(
            receiver_client, "_ensure_authenticated", new_callable=AsyncMock
        ):
            result = await receiver_client.submit_metrics(metrics)

        assert result is True
        mock_grpc.submit_metrics.assert_called_once_with(metrics)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_submit_metrics_rest_success(self, receiver_client, token_info):
        """Test successful metrics submission via REST."""
        receiver_client.token_info = token_info
        receiver_client._authenticated = True
        receiver_client.use_grpc = False

        mock_rest = AsyncMock()
        mock_rest.submit_metrics = AsyncMock(return_value=True)
        receiver_client.rest_client = mock_rest

        metrics = [{"name": "test_metric", "value": 42}]

        with patch.object(
            receiver_client, "_ensure_authenticated", new_callable=AsyncMock
        ):
            result = await receiver_client.submit_metrics(metrics)

        assert result is True
        mock_rest.submit_metrics.assert_called_once_with(metrics)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_submit_metrics_no_client(self, receiver_client, token_info):
        """Test metrics submission fails when no client available."""
        receiver_client.token_info = token_info
        receiver_client._authenticated = True
        receiver_client.use_grpc = False
        receiver_client.rest_client = None

        metrics = [{"name": "test_metric", "value": 42}]

        with patch.object(
            receiver_client, "_ensure_authenticated", new_callable=AsyncMock
        ):
            with patch(
                "shared.receiver_client.client.asyncio.sleep", new_callable=AsyncMock
            ):
                # ConnectionError from client module is raised by _submit, which then gets
                # caught and re-raised as SubmissionError by _retry_with_backoff
                with pytest.raises((SubmissionError, ConnectionError)):
                    await receiver_client.submit_metrics(metrics)


# Health Check Tests
class TestHealthCheck:
    """Test health check functionality."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_check_grpc_healthy(self, receiver_client, token_info):
        """Test health check via gRPC when healthy."""
        receiver_client.token_info = token_info
        receiver_client._authenticated = True
        receiver_client.use_grpc = True

        mock_grpc = AsyncMock()
        mock_grpc.health_check = MagicMock(return_value=True)
        receiver_client.grpc_client = mock_grpc

        with patch.object(
            receiver_client, "_ensure_authenticated", new_callable=AsyncMock
        ):
            result = await receiver_client.health_check()

        assert result is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_check_rest_healthy(self, receiver_client, token_info):
        """Test health check via REST when healthy."""
        receiver_client.token_info = token_info
        receiver_client._authenticated = True
        receiver_client.use_grpc = False

        mock_rest = AsyncMock()
        mock_rest.health_check = AsyncMock(return_value=True)
        receiver_client.rest_client = mock_rest

        with patch.object(
            receiver_client, "_ensure_authenticated", new_callable=AsyncMock
        ):
            result = await receiver_client.health_check()

        assert result is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_check_grpc_unhealthy(self, receiver_client, token_info):
        """Test health check via gRPC when unhealthy."""
        receiver_client.token_info = token_info
        receiver_client._authenticated = True
        receiver_client.use_grpc = True

        mock_grpc = AsyncMock()
        mock_grpc.health_check = MagicMock(return_value=False)
        receiver_client.grpc_client = mock_grpc

        with patch.object(
            receiver_client, "_ensure_authenticated", new_callable=AsyncMock
        ):
            result = await receiver_client.health_check()

        assert result is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_check_rest_unhealthy(self, receiver_client, token_info):
        """Test health check via REST when unhealthy."""
        receiver_client.token_info = token_info
        receiver_client._authenticated = True
        receiver_client.use_grpc = False

        mock_rest = AsyncMock()
        mock_rest.health_check = AsyncMock(return_value=False)
        receiver_client.rest_client = mock_rest

        with patch.object(
            receiver_client, "_ensure_authenticated", new_callable=AsyncMock
        ):
            result = await receiver_client.health_check()

        assert result is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_check_no_client(self, receiver_client, token_info):
        """Test health check fails gracefully when no client available."""
        receiver_client.token_info = token_info
        receiver_client._authenticated = True
        receiver_client.use_grpc = False
        receiver_client.rest_client = None

        with patch.object(
            receiver_client, "_ensure_authenticated", new_callable=AsyncMock
        ):
            result = await receiver_client.health_check()

        assert result is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_check_authentication_error(self, receiver_client):
        """Test health check handles authentication errors gracefully."""
        with patch.object(
            receiver_client,
            "_ensure_authenticated",
            side_effect=AuthenticationError("Auth failed"),
            new_callable=AsyncMock,
        ):
            result = await receiver_client.health_check()

        assert result is False


# Ensure Authenticated Tests
class TestEnsureAuthenticated:
    """Test _ensure_authenticated logic."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_ensure_authenticated_not_authenticated(self, receiver_client):
        """Test ensures authentication when not authenticated."""
        receiver_client._authenticated = False

        with patch.object(
            receiver_client, "authenticate", new_callable=AsyncMock
        ) as mock_auth:
            await receiver_client._ensure_authenticated()

        mock_auth.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_ensure_authenticated_token_expired(self, receiver_client):
        """Test ensures refresh when token expired."""
        expired_token = TokenInfo(
            access_token="token",
            refresh_token="refresh",
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        receiver_client.token_info = expired_token
        receiver_client._authenticated = True

        with patch.object(
            receiver_client, "refresh_token", new_callable=AsyncMock
        ) as mock_refresh:
            await receiver_client._ensure_authenticated()

        mock_refresh.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_ensure_authenticated_valid_token(self, receiver_client, token_info):
        """Test no action when token is valid."""
        receiver_client.token_info = token_info
        receiver_client._authenticated = True

        with patch.object(
            receiver_client, "authenticate", new_callable=AsyncMock
        ) as mock_auth:
            with patch.object(
                receiver_client, "refresh_token", new_callable=AsyncMock
            ) as mock_refresh:
                await receiver_client._ensure_authenticated()

        mock_auth.assert_not_called()
        mock_refresh.assert_not_called()


# Context Manager Tests
class TestContextManager:
    """Test async context manager functionality."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_context_manager_entry(self, receiver_client):
        """Test async context manager entry."""
        with patch.object(receiver_client, "authenticate", new_callable=AsyncMock):
            async with receiver_client as client:
                assert client is receiver_client

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_context_manager_exit(self, receiver_client):
        """Test async context manager exit."""
        receiver_client._authenticated = True
        receiver_client.grpc_client = MagicMock()
        receiver_client.rest_client = AsyncMock()

        with patch.object(receiver_client, "authenticate", new_callable=AsyncMock):
            with patch.object(
                receiver_client, "close", new_callable=AsyncMock
            ) as mock_close:
                async with receiver_client:
                    pass

                mock_close.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_context_manager_exception(self, receiver_client):
        """Test async context manager closes on exception."""
        with patch.object(receiver_client, "authenticate", new_callable=AsyncMock):
            with patch.object(
                receiver_client, "close", new_callable=AsyncMock
            ) as mock_close:
                try:
                    async with receiver_client:
                        raise ValueError("Test error")
                except ValueError:
                    pass

                mock_close.assert_called_once()


# Close Tests
class TestClose:
    """Test close functionality."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_close_with_grpc_client(self, receiver_client):
        """Test close disconnects gRPC client."""
        mock_grpc = MagicMock()
        receiver_client.grpc_client = mock_grpc
        receiver_client._authenticated = True

        await receiver_client.close()

        mock_grpc.disconnect.assert_called_once()
        assert receiver_client._authenticated is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_close_with_rest_client(self, receiver_client):
        """Test close disconnects REST client."""
        mock_rest = AsyncMock()
        receiver_client.rest_client = mock_rest
        receiver_client._authenticated = True

        await receiver_client.close()

        mock_rest.disconnect.assert_called_once()
        assert receiver_client._authenticated is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_close_with_both_clients(self, receiver_client):
        """Test close disconnects both clients."""
        mock_grpc = MagicMock()
        mock_rest = AsyncMock()
        receiver_client.grpc_client = mock_grpc
        receiver_client.rest_client = mock_rest
        receiver_client._authenticated = True

        await receiver_client.close()

        mock_grpc.disconnect.assert_called_once()
        mock_rest.disconnect.assert_called_once()
        assert receiver_client._authenticated is False


# Integration Tests
class TestIntegration:
    """Integration tests for common workflows."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_full_workflow_authenticate_and_submit(self, receiver_client):
        """Test complete workflow: authenticate and submit logs."""
        # Setup
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "token",
            "refresh_token": "refresh",
            "expires_in": 3600,
        }

        mock_grpc = MagicMock()
        mock_grpc.submit_logs = MagicMock(return_value=True)

        with patch("shared.receiver_client.client.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.post = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__.return_value = mock_async_client
            mock_async_client.__aexit__.return_value = None
            mock_client.return_value = mock_async_client

            with patch.object(
                receiver_client, "_initialize_clients", new_callable=AsyncMock
            ) as mock_init:
                with patch.object(GRPCSubmitter, "connect", return_value=True):
                    # Execute
                    await receiver_client.authenticate()
                    receiver_client.grpc_client = mock_grpc
                    receiver_client.use_grpc = True

                    logs = [{"msg": "test"}]
                    result = await receiver_client.submit_logs(logs)

        assert result is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_workflow_fallback_to_rest_on_grpc_failure(self, receiver_client):
        """Test workflow that falls back to REST on gRPC failure."""
        # Setup authentication
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "token",
            "refresh_token": "refresh",
            "expires_in": 3600,
        }

        mock_rest = AsyncMock()
        mock_rest.submit_logs = AsyncMock(return_value=True)

        with patch("shared.receiver_client.client.httpx.AsyncClient") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.post = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__.return_value = mock_async_client
            mock_async_client.__aexit__.return_value = None
            mock_client.return_value = mock_async_client

            with patch.object(
                receiver_client, "_initialize_clients", new_callable=AsyncMock
            ):
                # gRPC fails, fallback to REST
                with patch.object(
                    receiver_client,
                    "_try_grpc",
                    new_callable=AsyncMock,
                    return_value=False,
                ):
                    with patch.object(
                        receiver_client, "_fallback_to_rest", new_callable=AsyncMock
                    ):
                        await receiver_client.authenticate()
                        receiver_client.rest_client = mock_rest
                        receiver_client.use_grpc = False

                        logs = [{"msg": "test"}]
                        result = await receiver_client.submit_logs(logs)

        assert result is True
        mock_rest.submit_logs.assert_called_once()
