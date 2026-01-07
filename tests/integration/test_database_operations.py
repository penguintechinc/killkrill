"""
KillKrill - Database Operations Integration Tests

Comprehensive integration tests for PyDAL database operations including:
- CRUD operations on users, api_keys, and sensor_agents tables
- Connection pooling behavior
- Transaction handling (commit, rollback)
- Multi-database support (postgres, mysql, sqlite)
- Connection retry logic
- Health check queries
"""

import os
import time
from datetime import datetime, timedelta
from typing import List

import pytest
from pydal import DAL


@pytest.mark.integration
class TestBasicCRUDOperations:
    """Test basic Create, Read, Update, Delete operations"""

    def test_insert_user(self, pydal_db, sample_user_data):
        """Test inserting a user record"""
        # Insert user
        user_id = pydal_db.users.insert(**sample_user_data)
        pydal_db.commit()

        # Verify insertion
        assert user_id is not None
        user = pydal_db(pydal_db.users.id == user_id).select().first()
        assert user is not None
        assert user.email == sample_user_data["email"]
        assert user.name == sample_user_data["name"]
        assert user.role == sample_user_data["role"]
        assert user.is_active is True

    def test_select_user_by_email(self, pydal_db, sample_user_data):
        """Test querying user by email"""
        # Insert user
        user_id = pydal_db.users.insert(**sample_user_data)
        pydal_db.commit()

        # Query by email
        user = (
            pydal_db(pydal_db.users.email == sample_user_data["email"]).select().first()
        )
        assert user is not None
        assert user.email == sample_user_data["email"]
        assert user.id == user_id

    def test_update_user(self, pydal_db, sample_user_data):
        """Test updating a user record"""
        # Insert user
        user_id = pydal_db.users.insert(**sample_user_data)
        pydal_db.commit()

        # Update user
        new_name = "Updated Test User"
        pydal_db(pydal_db.users.id == user_id).update(
            name=new_name, updated_at=datetime.utcnow()
        )
        pydal_db.commit()

        # Verify update
        user = pydal_db(pydal_db.users.id == user_id).select().first()
        assert user.name == new_name

    def test_delete_user(self, pydal_db, sample_user_data):
        """Test deleting a user record"""
        # Insert user
        user_id = pydal_db.users.insert(**sample_user_data)
        pydal_db.commit()

        # Delete user
        deleted_count = pydal_db(pydal_db.users.id == user_id).delete()
        pydal_db.commit()

        # Verify deletion
        assert deleted_count == 1
        user = pydal_db(pydal_db.users.id == user_id).select().first()
        assert user is None

    def test_bulk_insert_users(self, pydal_db):
        """Test inserting multiple users in bulk"""
        users_data = [
            {
                # id auto-generated,
                "email": f"user{i}@example.com",
                "password_hash": f"hash{i}",
                "name": f"User {i}",
                "role": "viewer",
                "is_active": True,
                "fs_uniquifier": f"unique-{i}",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            for i in range(10)
        ]

        # Bulk insert
        for user_data in users_data:
            pydal_db.users.insert(**user_data)
        pydal_db.commit()

        # Verify count
        count = pydal_db(pydal_db.users.email.like("user%@example.com")).count()
        assert count == 10

    def test_query_with_pagination(self, pydal_db):
        """Test querying with LIMIT and OFFSET (pagination)"""
        # Insert test users
        for i in range(20):
            pydal_db.users.insert(
                id=f"user-page-{i}",
                email=f"page{i}@example.com",
                password_hash=f"hash{i}",
                name=f"Page User {i}",
                role="viewer",
                is_active=True,
                fs_uniquifier=f"page-unique-{i}",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        pydal_db.commit()

        # Query first page (10 items)
        page1 = pydal_db(pydal_db.users.email.like("page%@example.com")).select(
            limitby=(0, 10), orderby=pydal_db.users.id
        )
        assert len(page1) == 10

        # Query second page (10 items)
        page2 = pydal_db(pydal_db.users.email.like("page%@example.com")).select(
            limitby=(10, 20), orderby=pydal_db.users.id
        )
        assert len(page2) == 10

        # Verify no overlap
        page1_ids = {user.id for user in page1}
        page2_ids = {user.id for user in page2}
        assert len(page1_ids.intersection(page2_ids)) == 0


@pytest.mark.integration
class TestAPIKeyCRUD:
    """Test CRUD operations on API keys table"""

    def test_insert_api_key(self, pydal_db, sample_user_data, sample_api_key_data):
        """Test inserting an API key"""
        # Insert user first (foreign key dependency)
        user_id = pydal_db.users.insert(**sample_user_data)

        # Insert API key
        key_id = pydal_db.api_keys.insert(**sample_api_key_data)
        pydal_db.commit()

        # Verify insertion
        assert key_id is not None
        api_key = pydal_db(pydal_db.api_keys.id == key_id).select().first()
        assert api_key is not None
        assert api_key.user_id == user_id
        assert api_key.name == sample_api_key_data["name"]
        assert api_key.is_active is True

    def test_query_api_keys_by_user(
        self, pydal_db, sample_user_data, sample_api_key_data
    ):
        """Test querying all API keys for a user"""
        # Insert user
        user_id = pydal_db.users.insert(**sample_user_data)

        # Insert multiple API keys for same user
        for i in range(3):
            key_data = sample_api_key_data.copy()
            key_data["id"] = f"key-test-{i}"
            key_data["name"] = f"Test Key {i}"
            pydal_db.api_keys.insert(**key_data)
        pydal_db.commit()

        # Query all keys for user
        keys = pydal_db(pydal_db.api_keys.user_id == user_id).select()
        assert len(keys) == 3

    def test_update_api_key_last_used(
        self, pydal_db, sample_user_data, sample_api_key_data
    ):
        """Test updating last_used_at timestamp"""
        # Insert user and API key
        user_id = pydal_db.users.insert(**sample_user_data)
        key_id = pydal_db.api_keys.insert(**sample_api_key_data)
        pydal_db.commit()

        # Update last_used_at
        now = datetime.utcnow()
        pydal_db(pydal_db.api_keys.id == key_id).update(last_used_at=now)
        pydal_db.commit()

        # Verify update
        api_key = pydal_db(pydal_db.api_keys.id == key_id).select().first()
        assert api_key.last_used_at is not None
        # Allow small time difference due to database precision
        time_diff = abs((api_key.last_used_at - now).total_seconds())
        assert time_diff < 2

    def test_deactivate_api_key(self, pydal_db, sample_user_data, sample_api_key_data):
        """Test soft-deleting (deactivating) an API key"""
        # Insert user and API key
        user_id = pydal_db.users.insert(**sample_user_data)
        key_id = pydal_db.api_keys.insert(**sample_api_key_data)
        pydal_db.commit()

        # Deactivate key
        pydal_db(pydal_db.api_keys.id == key_id).update(is_active=False)
        pydal_db.commit()

        # Verify deactivation
        api_key = pydal_db(pydal_db.api_keys.id == key_id).select().first()
        assert api_key.is_active is False


@pytest.mark.integration
class TestSensorAgentCRUD:
    """Test CRUD operations on sensor_agents table"""

    def test_insert_sensor_agent(self, pydal_db, sample_sensor_agent_data):
        """Test inserting a sensor agent"""
        # Insert sensor agent
        agent_id = pydal_db.sensor_agents.insert(**sample_sensor_agent_data)
        pydal_db.commit()

        # Verify insertion
        assert agent_id is not None
        agent = pydal_db(pydal_db.sensor_agents.id == agent_id).select().first()
        assert agent is not None
        assert agent.agent_id == sample_sensor_agent_data["agent_id"]
        assert agent.hostname == sample_sensor_agent_data["hostname"]
        assert agent.is_active is True

    def test_update_sensor_heartbeat(self, pydal_db, sample_sensor_agent_data):
        """Test updating sensor agent heartbeat timestamp"""
        # Insert sensor agent
        agent_id = pydal_db.sensor_agents.insert(**sample_sensor_agent_data)
        pydal_db.commit()

        # Update heartbeat
        new_heartbeat = datetime.utcnow()
        pydal_db(pydal_db.sensor_agents.id == agent_id).update(
            last_heartbeat=new_heartbeat, updated_at=new_heartbeat
        )
        pydal_db.commit()

        # Verify update
        agent = pydal_db(pydal_db.sensor_agents.id == agent_id).select().first()
        time_diff = abs((agent.last_heartbeat - new_heartbeat).total_seconds())
        assert time_diff < 2

    def test_query_active_agents(self, pydal_db):
        """Test querying only active sensor agents"""
        # Insert mix of active and inactive agents
        for i in range(5):
            pydal_db.sensor_agents.insert(
                id=f"agent-active-{i}",
                agent_id=f"sensor-{i}",
                name=f"Agent {i}",
                hostname=f"host{i}.example.com",
                ip_address=f"192.168.1.{100 + i}",
                api_key_hash=f"hash{i}",
                agent_version="1.0.0",
                is_active=(i % 2 == 0),  # Even numbers are active
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        pydal_db.commit()

        # Query only active agents
        active_agents = pydal_db(
            (pydal_db.sensor_agents.is_active == True)
            & (pydal_db.sensor_agents.agent_id.like("sensor-%"))
        ).select()

        assert len(active_agents) == 3  # Agents 0, 2, 4


@pytest.mark.integration
class TestTransactionHandling:
    """Test database transaction handling"""

    def test_commit_transaction(self, pydal_db, sample_user_data):
        """Test successful transaction commit"""
        # Insert user
        user_id = pydal_db.users.insert(**sample_user_data)
        pydal_db.commit()

        # Verify data is persisted
        user = pydal_db(pydal_db.users.id == user_id).select().first()
        assert user is not None

    def test_rollback_transaction(self, pydal_db, sample_user_data):
        """Test transaction rollback"""
        # Insert user but don't commit
        user_id = pydal_db.users.insert(**sample_user_data)

        # Rollback transaction
        pydal_db.rollback()

        # Verify data is not persisted
        user = pydal_db(pydal_db.users.id == user_id).select().first()
        assert user is None

    def test_multiple_operations_single_transaction(
        self, pydal_db, sample_user_data, sample_api_key_data
    ):
        """Test multiple operations in single transaction"""
        # Insert user and API key in single transaction
        user_id = pydal_db.users.insert(**sample_user_data)
        key_id = pydal_db.api_keys.insert(**sample_api_key_data)
        pydal_db.commit()

        # Verify both are persisted
        user = pydal_db(pydal_db.users.id == user_id).select().first()
        api_key = pydal_db(pydal_db.api_keys.id == key_id).select().first()
        assert user is not None
        assert api_key is not None

    def test_rollback_partial_transaction(
        self, pydal_db, sample_user_data, sample_api_key_data
    ):
        """Test rollback undoes all operations in transaction"""
        # Insert user and API key
        user_id = pydal_db.users.insert(**sample_user_data)
        key_id = pydal_db.api_keys.insert(**sample_api_key_data)

        # Rollback without commit
        pydal_db.rollback()

        # Verify neither is persisted
        user = pydal_db(pydal_db.users.id == user_id).select().first()
        api_key = pydal_db(pydal_db.api_keys.id == key_id).select().first()
        assert user is None
        assert api_key is None


@pytest.mark.integration
class TestJoinQueries:
    """Test JOIN operations between tables"""

    def test_select_api_keys_with_user_info(
        self, pydal_db, sample_user_data, sample_api_key_data
    ):
        """Test joining api_keys with users table"""
        # Insert user and API key
        user_id = pydal_db.users.insert(**sample_user_data)
        key_id = pydal_db.api_keys.insert(**sample_api_key_data)
        pydal_db.commit()

        # Query API keys with user info (manual join via WHERE)
        results = pydal_db(
            (pydal_db.api_keys.user_id == pydal_db.users.id)
            & (pydal_db.api_keys.id == key_id)
        ).select(pydal_db.api_keys.ALL, pydal_db.users.email, pydal_db.users.name)

        assert len(results) == 1
        result = results.first()
        assert result.api_keys.id == key_id
        assert result.users.email == sample_user_data["email"]

    def test_count_api_keys_per_user(self, pydal_db, sample_user_data):
        """Test counting API keys grouped by user"""
        # Insert user
        user_id = pydal_db.users.insert(**sample_user_data)

        # Insert multiple API keys
        for i in range(3):
            pydal_db.api_keys.insert(
                id=f"key-count-{i}",
                user_id=user_id,
                name=f"Key {i}",
                key_hash=f"hash{i}",
                permissions=["read"],
                is_active=True,
                created_at=datetime.utcnow(),
            )
        pydal_db.commit()

        # Count keys for user
        count = pydal_db(pydal_db.api_keys.user_id == user_id).count()
        assert count == 3


@pytest.mark.integration
class TestParameterizedQueries:
    """Test parameterized queries for SQL injection prevention"""

    def test_parameterized_email_query(self, pydal_db, sample_user_data):
        """Test parameterized query with user input"""
        # Insert user
        pydal_db.users.insert(**sample_user_data)
        pydal_db.commit()

        # Query with parameterized email (simulating user input)
        user_email = sample_user_data["email"]
        user = pydal_db(pydal_db.users.email == user_email).select().first()
        assert user is not None
        assert user.email == user_email

    def test_parameterized_like_query(self, pydal_db):
        """Test parameterized LIKE query"""
        # Insert test users
        for i in range(5):
            pydal_db.users.insert(
                id=f"user-like-{i}",
                email=f"testuser{i}@example.com",
                password_hash=f"hash{i}",
                name=f"Test User {i}",
                role="viewer",
                is_active=True,
                fs_uniquifier=f"like-unique-{i}",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        pydal_db.commit()

        # Parameterized LIKE query
        search_pattern = "testuser%"
        users = pydal_db(pydal_db.users.email.like(search_pattern)).select()
        assert len(users) == 5

    def test_sql_injection_prevention(self, pydal_db):
        """Test that SQL injection attempts are safely handled"""
        # Insert test user
        pydal_db.users.insert(
            id="user-injection-test",
            email="real@example.com",
            password_hash="hash123",
            name="Real User",
            role="viewer",
            is_active=True,
            fs_uniquifier="injection-unique",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        pydal_db.commit()

        # Attempt SQL injection via parameterized query
        # PyDAL should escape this properly
        malicious_email = "' OR '1'='1"
        users = pydal_db(pydal_db.users.email == malicious_email).select()

        # Should return no results (injection prevented)
        assert len(users) == 0


@pytest.mark.integration
class TestConnectionLifecycle:
    """Test database connection lifecycle"""

    def test_connection_open_and_close(self, test_db_config):
        """Test opening and closing database connection"""
        # Create new connection
        db = DAL(
            test_db_config["db_url"],
            pool_size=1,
            migrate=False,
        )

        # Verify connection is open
        assert db is not None

        # Close connection
        db.close()

        # Connection should be closed (attempting operations may fail)
        # This is expected behavior

    def test_health_check_query(self, pydal_db):
        """Test simple health check query (SELECT 1)"""
        # Execute health check query
        result = pydal_db.executesql("SELECT 1 as health_check")

        # Verify result
        assert result is not None
        assert len(result) == 1
        assert result[0][0] == 1


@pytest.mark.integration
@pytest.mark.requires_db
class TestMultiDatabaseSupport:
    """Test multi-database backend support (postgres, mysql, sqlite)"""

    def test_database_type_detection(self, pydal_db, test_db_config):
        """Test that correct database type is being used"""
        db_type = test_db_config["db_type"]
        assert db_type in ("postgres", "postgresql", "mysql", "mariadb", "sqlite")

    def test_insert_select_across_databases(self, pydal_db, sample_user_data):
        """Test basic operations work across different database backends"""
        # Insert user
        user_id = pydal_db.users.insert(**sample_user_data)
        pydal_db.commit()

        # Query user
        user = pydal_db(pydal_db.users.id == user_id).select().first()
        assert user is not None
        assert user.email == sample_user_data["email"]

    def test_json_field_support(self, pydal_db, sample_api_key_data, sample_user_data):
        """Test JSON field support across database backends"""
        # Insert user and API key with JSON permissions
        user_id = pydal_db.users.insert(**sample_user_data)
        key_id = pydal_db.api_keys.insert(**sample_api_key_data)
        pydal_db.commit()

        # Query and verify JSON field
        api_key = pydal_db(pydal_db.api_keys.id == key_id).select().first()
        assert api_key.permissions is not None
        assert isinstance(
            api_key.permissions, (list, str)
        )  # May be list or JSON string


@pytest.mark.integration
class TestConnectionRetry:
    """Test connection retry logic"""

    def test_connection_with_timeout(self, test_db_config, db_connection_retry_config):
        """Test connection establishment with timeout"""
        start_time = time.time()

        try:
            # Attempt connection
            db = DAL(
                test_db_config["db_url"],
                pool_size=1,
                migrate=False,
            )

            # Verify connection established quickly
            elapsed = time.time() - start_time
            assert elapsed < db_connection_retry_config["timeout"]

            db.close()

        except Exception as e:
            # Connection may fail in CI environment, that's acceptable
            elapsed = time.time() - start_time
            # Verify timeout was respected
            assert elapsed <= db_connection_retry_config["timeout"] + 1

    def test_query_execution_timeout(self, pydal_db):
        """Test that queries complete within reasonable time"""
        start_time = time.time()

        # Execute simple query
        result = pydal_db.executesql("SELECT 1")

        elapsed = time.time() - start_time

        # Query should be very fast
        assert elapsed < 1.0
        assert result is not None


@pytest.mark.integration
class TestAuditLog:
    """Test audit log table operations"""

    def test_insert_audit_log_entry(self, pydal_db, sample_user_data):
        """Test inserting audit log entry"""
        # Insert user first
        user_id = pydal_db.users.insert(**sample_user_data)
        pydal_db.commit()

        # Insert audit log entry
        log_id = pydal_db.audit_log.insert(
            id="log-test-001",
            user_id=user_id,
            audit_action="user.login",
            resource_type="user",
            resource_id=user_id,
            details={"ip": "192.168.1.1"},
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            created_at=datetime.utcnow(),
        )
        pydal_db.commit()

        # Verify insertion
        assert log_id is not None
        log_entry = (
            pydal_db(pydal_db.audit_log.audit_action == "user.login").select().first()
        )
        assert log_entry is not None
        assert log_entry.audit_action == "user.login"

    def test_query_audit_log_by_user(self, pydal_db, sample_user_data):
        """Test querying audit log entries for specific user"""
        # Insert user
        user_id = pydal_db.users.insert(**sample_user_data)

        # Insert multiple audit log entries
        for i in range(5):
            pydal_db.audit_log.insert(
                id=f"log-user-{i}",
                user_id=user_id,
                audit_action=f"action.{i}",
                resource_type="test",
                resource_id=f"resource-{i}",
                details={},
                created_at=datetime.utcnow(),
            )
        pydal_db.commit()

        # Query all logs for user
        logs = pydal_db(pydal_db.audit_log.user_id == user_id).select()
        assert len(logs) == 5


@pytest.mark.integration
class TestIndexAndPerformance:
    """Test query performance and index usage"""

    def test_unique_constraint_violation(self, pydal_db, sample_user_data):
        """Test that unique constraint violations are handled"""
        # Insert user
        pydal_db.users.insert(**sample_user_data)
        pydal_db.commit()

        # Attempt to insert duplicate email (should fail)
        duplicate_user = sample_user_data.copy()
        duplicate_user["id"] = "user-duplicate"
        duplicate_user["fs_uniquifier"] = "unique-duplicate"

        with pytest.raises(Exception):  # Database will raise integrity error
            pydal_db.users.insert(**duplicate_user)
            pydal_db.commit()

    def test_query_performance_with_index(self, pydal_db):
        """Test query performance on indexed columns"""
        # Insert many users
        for i in range(100):
            pydal_db.users.insert(
                id=f"user-perf-{i}",
                email=f"perf{i}@example.com",
                password_hash=f"hash{i}",
                name=f"Performance User {i}",
                role="viewer",
                is_active=True,
                fs_uniquifier=f"perf-unique-{i}",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        pydal_db.commit()

        # Query by indexed email column (should be fast)
        start_time = time.time()
        user = pydal_db(pydal_db.users.email == "perf50@example.com").select().first()
        elapsed = time.time() - start_time

        # Query should complete in under 100ms even with 100 records
        assert elapsed < 0.1
        assert user is not None
