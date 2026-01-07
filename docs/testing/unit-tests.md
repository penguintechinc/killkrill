# Unit Testing Guide

Unit tests verify individual functions and methods in isolation using mocked external dependencies (databases, queues, external APIs).

## Goals & Requirements

- **Speed**: <1 second per test (total suite <60 seconds)
- **Isolation**: No network calls, no database access, no side effects
- **Coverage**: ≥85% of module logic
- **Clarity**: Single responsibility, explicit assertions
- **Maintainability**: Use fixtures for common patterns

## Test Structure

### File Organization

```
tests/unit/
├── conftest.py                     # Unit-level fixtures
├── shared/                         # Shared utilities
│   ├── test_validators.py
│   ├── test_serializers.py
│   └── test_config.py
├── log-worker/
│   ├── test_parsing.py
│   ├── test_validation.py
│   ├── test_transformation.py
│   └── test_error_handling.py
├── metrics-worker/
│   ├── test_parsing.py
│   ├── test_aggregation.py
│   ├── test_output.py
│   └── test_error_handling.py
├── receivers/
│   ├── test_http_receiver.py
│   ├── test_syslog_receiver.py
│   ├── test_auth.py
│   └── test_validation.py
└── manager/
    ├── test_api.py
    ├── test_auth.py
    └── test_models.py
```

### Naming Convention

- File: `test_<module>.py`
- Test class: `Test<Feature>` (optional, group related tests)
- Test function: `test_<what>_<condition>_<expected>`

Example:
```python
# tests/unit/log-worker/test_parsing.py

def test_parse_valid_json_log_with_all_fields():
    """When parsing valid log with all fields, should succeed"""

def test_parse_invalid_timestamp_raises_error():
    """When parsing invalid timestamp, should raise ParseError"""

def test_parse_missing_required_field_raises_error():
    """When required field missing, should raise ParseError"""

class TestLogLevelMapping:
    def test_maps_info_to_uppercase(self):
        pass

    def test_maps_debug_to_uppercase(self):
        pass
```

## Fixtures & Mocking

### Common Unit Test Fixtures

Define in `tests/unit/conftest.py`:

```python
import pytest
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_redis():
    """Mocked Redis client for unit tests"""
    return MagicMock()

@pytest.fixture
def mock_elasticsearch():
    """Mocked Elasticsearch client"""
    return MagicMock()

@pytest.fixture
def mock_logger():
    """Mocked logger"""
    return MagicMock()

@pytest.fixture
def sample_log_entry():
    """Sample log entry data"""
    return {
        "timestamp": "2024-01-06T12:00:00Z",
        "service": "test-service",
        "level": "info",
        "message": "Test log message"
    }

@pytest.fixture
def sample_metric():
    """Sample metric data"""
    return {
        "name": "http_requests_total",
        "value": 1000,
        "labels": {"service": "api", "endpoint": "/health"},
        "timestamp": 1704528000
    }
```

### Mocking Patterns

**Mock External Services**:
```python
@patch('log_worker.worker.redis.Redis')
@patch('log_worker.worker.elasticsearch.Elasticsearch')
def test_worker_processes_logs(mock_es, mock_redis):
    """Test with mocked Redis and Elasticsearch"""
    mock_redis.return_value.xread.return_value = [...]
    mock_es.return_value.bulk.return_value = True

    worker = LogWorker()
    worker.process_batch()

    assert mock_redis.return_value.xread.called
    assert mock_es.return_value.bulk.called
```

**Mock Database Operations**:
```python
@patch('shared.database.db')
def test_user_creation(mock_db):
    """Test user model without database"""
    mock_db.users.insert.return_value = 123

    user_id = create_user("test@example.com", "password")

    assert user_id == 123
    mock_db.users.insert.assert_called_once()
```

**Spy on Calls**:
```python
from unittest.mock import call

def test_multiple_log_processing():
    """Verify function called multiple times with different args"""
    with patch('elasticsearch.Elasticsearch.bulk') as mock_bulk:
        process_logs([log1, log2, log3])

        # Verify called exactly 3 times
        assert mock_bulk.call_count == 3

        # Verify call arguments
        first_call = mock_bulk.call_args_list[0]
        assert 'index' in first_call.kwargs
```

## Test Patterns by Component

### 1. Data Validation Tests

```python
import pytest
from log_worker.validation import LogValidator, ValidationError

class TestLogValidation:
    @pytest.fixture
    def validator(self):
        return LogValidator()

    def test_valid_log_passes(self, validator):
        """Valid log should pass validation"""
        log = {
            "timestamp": "2024-01-06T12:00:00Z",
            "service": "api",
            "level": "info",
            "message": "Test"
        }
        assert validator.validate(log) is True

    @pytest.mark.parametrize("missing_field", [
        "timestamp", "service", "level", "message"
    ])
    def test_missing_field_raises_error(self, validator, missing_field):
        """Missing required field should raise ValidationError"""
        log = {
            "timestamp": "2024-01-06T12:00:00Z",
            "service": "api",
            "level": "info",
            "message": "Test"
        }
        del log[missing_field]

        with pytest.raises(ValidationError) as exc:
            validator.validate(log)

        assert missing_field in str(exc.value)

    def test_invalid_timestamp_format(self, validator):
        """Invalid timestamp format should raise error"""
        log = {
            "timestamp": "invalid",
            "service": "api",
            "level": "info",
            "message": "Test"
        }

        with pytest.raises(ValidationError):
            validator.validate(log)

    def test_invalid_log_level_raises_error(self, validator):
        """Invalid log level should raise error"""
        log = {
            "timestamp": "2024-01-06T12:00:00Z",
            "service": "api",
            "level": "invalid_level",
            "message": "Test"
        }

        with pytest.raises(ValidationError):
            validator.validate(log)
```

### 2. Data Parsing Tests

```python
from log_worker.parser import LogParser, ParseError

def test_parse_json_log():
    """Parse valid JSON log entry"""
    parser = LogParser()
    log_json = '{"timestamp":"2024-01-06T12:00:00Z","service":"api","level":"info","message":"Test"}'

    result = parser.parse(log_json)

    assert result.timestamp == "2024-01-06T12:00:00Z"
    assert result.service == "api"
    assert result.level == "info"
    assert result.message == "Test"

def test_parse_syslog_entry():
    """Parse syslog format entry"""
    parser = LogParser()
    syslog = "<14>Jan  6 12:00:00 host service[123]: User login"

    result = parser.parse_syslog(syslog)

    assert result.service == "service"
    assert result.pid == "123"
    assert result.message == "User login"

def test_parse_invalid_json_raises_error():
    """Invalid JSON should raise ParseError"""
    parser = LogParser()
    invalid_json = '{"timestamp":"invalid json"'

    with pytest.raises(ParseError):
        parser.parse(invalid_json)
```

### 3. Transformation Tests

```python
from log_worker.transformer import LogTransformer

class TestLogTransformation:
    def test_normalize_log_levels(self):
        """Normalize various level formats to uppercase"""
        transformer = LogTransformer()

        assert transformer.normalize_level("Info") == "INFO"
        assert transformer.normalize_level("DEBUG") == "DEBUG"
        assert transformer.normalize_level("error") == "ERROR"

    def test_extract_fields_from_message(self):
        """Extract key=value pairs from log message"""
        transformer = LogTransformer()
        msg = "user=alice status=active timestamp=2024-01-06"

        result = transformer.extract_fields(msg)

        assert result["user"] == "alice"
        assert result["status"] == "active"
        assert result["timestamp"] == "2024-01-06"

    def test_add_metadata_to_log(self):
        """Add environment and version metadata"""
        transformer = LogTransformer(env="production", version="1.2.0")
        log = {"message": "Test"}

        result = transformer.add_metadata(log)

        assert result["environment"] == "production"
        assert result["version"] == "1.2.0"
```

### 4. Authentication Tests

```python
from shared.auth import hash_password, verify_password, generate_token

def test_password_hashing():
    """Password should be hashed securely"""
    password = "secure_password_123"

    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)

def test_verify_wrong_password():
    """Verify should fail with wrong password"""
    password = "correct_password"
    hashed = hash_password(password)

    assert not verify_password("wrong_password", hashed)

def test_generate_jwt_token():
    """Generate valid JWT token"""
    user_id = 123
    secret = "test_secret"

    token = generate_token(user_id, secret)

    assert token is not None
    assert len(token) > 0
```

### 5. Error Handling Tests

```python
from log_worker.processor import LogProcessor

@pytest.mark.parametrize("error_type,error_msg", [
    ("timeout", "Redis connection timeout"),
    ("invalid_data", "Cannot parse log data"),
    ("missing_field", "Required field missing"),
])
def test_processor_handles_errors(error_type, error_msg):
    """Processor should handle various error conditions"""
    processor = LogProcessor()

    with pytest.raises(ProcessingError) as exc:
        processor.process(create_mock_log(error_type))

    assert error_msg in str(exc.value)
```

## Parametrized Tests

Test multiple inputs with single test function:

```python
@pytest.mark.parametrize("input_val,expected", [
    ("info", "INFO"),
    ("INFO", "INFO"),
    ("Info", "INFO"),
    ("debug", "DEBUG"),
    ("error", "ERROR"),
])
def test_normalize_log_levels(input_val, expected):
    """Normalize all log level variations"""
    result = normalize_level(input_val)
    assert result == expected

# Test with multiple parameters
@pytest.mark.parametrize("timestamp,service,level", [
    ("2024-01-06T12:00:00Z", "api", "info"),
    ("2024-01-06T12:00:01Z", "worker", "error"),
    ("2024-01-06T12:00:02Z", "manager", "debug"),
])
def test_parse_various_logs(timestamp, service, level):
    """Parse various log combinations"""
    log = create_log(timestamp, service, level)
    assert log.timestamp == timestamp
```

## Coverage & Best Practices

### Check Coverage

```bash
# Generate coverage report
pytest --cov=services tests/unit/ --cov-report=html

# Check specific module
pytest --cov=log_worker tests/unit/log-worker/

# Show missing lines
pytest --cov=services --cov-report=term-missing tests/unit/
```

### Best Practices

1. **One assertion per test** (when possible)
   ```python
   # Good - single responsibility
   def test_parse_sets_timestamp():
       assert parser.parse(log).timestamp == expected

   def test_parse_sets_service():
       assert parser.parse(log).service == expected
   ```

2. **Use descriptive names**
   ```python
   # Good
   def test_parse_syslog_extracts_service_name_from_bracket():
       pass

   # Bad
   def test_parse():
       pass
   ```

3. **Mock external dependencies**
   ```python
   # Good - fully isolated
   @patch('log_worker.elasticsearch')
   def test_with_mock(mock_es):
       pass

   # Bad - depends on real service
   def test_without_mock():
       real_es = Elasticsearch(['localhost:9200'])
   ```

4. **Use fixtures for common setup**
   ```python
   # Good - DRY, reusable
   @pytest.fixture
   def sample_log():
       return {"timestamp": "...", "service": "..."}

   def test_parse(sample_log):
       assert parse(sample_log) is not None

   # Bad - repeated setup
   def test_parse_1():
       log = {"timestamp": "...", "service": "..."}

   def test_parse_2():
       log = {"timestamp": "...", "service": "..."}
   ```

5. **Avoid test interdependence**
   ```python
   # Good - independent tests
   def test_create_user():
       user = create_user("test@example.com")
       assert user.id > 0

   def test_get_user():
       user = get_user(123)
       assert user.email == "test@example.com"

   # Bad - depends on test order
   def test_1_create_user():
       global user_id
       user_id = create_user()

   def test_2_get_user():
       user = get_user(user_id)  # Depends on test_1
   ```

---

**Last Updated**: 2026-01-07
**Framework**: Pytest 7.0+, Python 3.12+
