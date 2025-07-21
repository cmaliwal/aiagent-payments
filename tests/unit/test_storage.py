import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from aiagent_payments.exceptions import ValidationError
from aiagent_payments.models import (
    PaymentPlan,
    PaymentTransaction,
    Subscription,
    UsageRecord,
)
from aiagent_payments.storage import DatabaseStorage, FileStorage, MemoryStorage, StorageBackend


def test_memory_storage_initialization():
    storage = MemoryStorage()
    assert storage is not None
    assert hasattr(storage, "payment_plans")
    assert hasattr(storage, "subscriptions")
    assert hasattr(storage, "usage_records")
    assert hasattr(storage, "transactions")


def test_memory_storage_payment_plans():
    storage = MemoryStorage()

    # Test save and get payment plan
    plan = PaymentPlan(id="test_plan", name="Test Plan", price=10.0)
    storage.save_payment_plan(plan)

    retrieved = storage.get_payment_plan("test_plan")
    assert retrieved is not None
    assert retrieved.id == "test_plan"
    assert retrieved.name == "Test Plan"
    assert retrieved.price == 10.0

    # Test get non-existent plan
    assert storage.get_payment_plan("nonexistent") is None

    # Test list payment plans
    plan2 = PaymentPlan(id="test_plan2", name="Test Plan 2", price=20.0)
    storage.save_payment_plan(plan2)

    plans = storage.list_payment_plans()
    assert len(plans) == 2
    plan_ids = [p.id for p in plans]
    assert "test_plan" in plan_ids
    assert "test_plan2" in plan_ids


def test_memory_storage_subscriptions():
    storage = MemoryStorage()

    # Test save and get subscription
    sub = Subscription(id="test_sub", user_id="user1", plan_id="test_plan", status="active")
    storage.save_subscription(sub)

    retrieved = storage.get_subscription("test_sub")
    assert retrieved is not None
    assert retrieved.id == "test_sub"
    assert retrieved.user_id == "user1"
    assert retrieved.plan_id == "test_plan"

    # Test get non-existent subscription
    assert storage.get_subscription("nonexistent") is None

    # Test get user subscription
    user_sub = storage.get_user_subscription("user1")
    assert user_sub is not None
    assert user_sub.id == "test_sub"

    # Test get non-existent user subscription
    assert storage.get_user_subscription("nonexistent") is None


def test_memory_storage_usage_records():
    storage = MemoryStorage()

    # Test save usage record
    record = UsageRecord(id="test_record", user_id="user1", feature="test_feature", cost=0.5)
    storage.save_usage_record(record)

    # Test get user usage
    record2 = UsageRecord(id="test_record2", user_id="user1", feature="test_feature2", cost=0.3)
    storage.save_usage_record(record2)

    user_records = storage.get_user_usage("user1")
    assert len(user_records) == 2

    # Test get user usage with date filtering
    start_date = datetime.now(timezone.utc)
    user_records_filtered = storage.get_user_usage("user1", start_date=start_date)
    assert len(user_records_filtered) == 0  # Records created before start_date


def test_memory_storage_transactions():
    storage = MemoryStorage()

    # Test save and get transaction
    transaction = PaymentTransaction(
        id="test_transaction",
        user_id="user1",
        amount=10.0,
        currency="USD",
        payment_method="stripe",
        status="completed",
    )
    storage.save_transaction(transaction)

    retrieved = storage.get_transaction("test_transaction")
    assert retrieved is not None
    assert retrieved.id == "test_transaction"
    assert retrieved.user_id == "user1"
    assert retrieved.amount == 10.0
    assert retrieved.currency == "USD"

    # Test get non-existent transaction
    assert storage.get_transaction("nonexistent") is None


def test_file_storage_initialization():
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FileStorage(temp_dir)
        assert storage is not None
        assert storage.data_dir == temp_dir
        # Files are created when first data is saved, not on initialization
        # Test that files can be created
        plan = PaymentPlan(id="test_plan", name="Test Plan", price=10.0)
        storage.save_payment_plan(plan)
        assert os.path.exists(os.path.join(temp_dir, "payment_plans.json"))


def test_file_storage_payment_plans():
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FileStorage(temp_dir)

        # Test save and get payment plan
        plan = PaymentPlan(id="test_plan", name="Test Plan", price=10.0)
        storage.save_payment_plan(plan)

        retrieved = storage.get_payment_plan("test_plan")
        assert retrieved is not None
        assert retrieved.id == "test_plan"
        assert retrieved.name == "Test Plan"
        assert retrieved.price == 10.0

        # Test get non-existent plan
        assert storage.get_payment_plan("nonexistent") is None

        # Test list payment plans
        plan2 = PaymentPlan(id="test_plan2", name="Test Plan 2", price=20.0)
        storage.save_payment_plan(plan2)

        plans = storage.list_payment_plans()
        assert len(plans) == 2

        # Verify files are created
        plan_file = os.path.join(temp_dir, "payment_plans.json")
        assert os.path.exists(plan_file)

        with open(plan_file) as f:
            data = json.load(f)
            assert len(data) == 2


def test_file_storage_subscriptions():
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FileStorage(temp_dir)

        # Test save and get subscription
        sub = Subscription(id="test_sub", user_id="user1", plan_id="test_plan", status="active")
        storage.save_subscription(sub)

        retrieved = storage.get_subscription("test_sub")
        assert retrieved is not None
        assert retrieved.id == "test_sub"
        assert retrieved.user_id == "user1"

        # Test get user subscription
        user_sub = storage.get_user_subscription("user1")
        assert user_sub is not None
        assert user_sub.id == "test_sub"


def test_file_storage_usage_records():
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FileStorage(temp_dir)

        # Test save usage record
        record = UsageRecord(id="test_record", user_id="user1", feature="test_feature", cost=0.5)
        storage.save_usage_record(record)

        # Test get user usage
        record2 = UsageRecord(id="test_record2", user_id="user1", feature="test_feature2", cost=0.3)
        storage.save_usage_record(record2)

        user_records = storage.get_user_usage("user1")
        assert len(user_records) == 2


def test_file_storage_transactions():
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FileStorage(temp_dir)

        # Test save and get transaction
        transaction = PaymentTransaction(
            id="test_transaction",
            user_id="user1",
            amount=10.0,
            currency="USD",
            payment_method="stripe",
            status="completed",
        )
        storage.save_transaction(transaction)

        retrieved = storage.get_transaction("test_transaction")
        assert retrieved is not None
        assert retrieved.id == "test_transaction"
        assert retrieved.user_id == "user1"
        assert retrieved.amount == 10.0


def test_file_storage_persistence():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create storage and add data
        storage1 = FileStorage(temp_dir)
        plan = PaymentPlan(id="test_plan", name="Test Plan", price=10.0)
        storage1.save_payment_plan(plan)

        # Create new storage instance (simulates restart)
        storage2 = FileStorage(temp_dir)

        # Data should persist
        retrieved = storage2.get_payment_plan("test_plan")
        assert retrieved is not None
        assert retrieved.id == "test_plan"


def test_file_storage_error_handling():
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FileStorage(temp_dir)

        # Test with invalid data directory
        with pytest.raises(Exception):
            FileStorage("/nonexistent/directory")

        # Test with corrupted JSON file
        plan_file = os.path.join(temp_dir, "payment_plans.json")
        with open(plan_file, "w") as f:
            f.write("invalid json")

        # Should handle corrupted file gracefully
        storage = FileStorage(temp_dir)
        plans = storage.list_payment_plans()
        assert len(plans) == 0


def test_storage_backend_abstract_methods():
    # Test that StorageBackend is abstract by trying to instantiate it
    from abc import ABC

    assert issubclass(StorageBackend, ABC)


def test_memory_storage_edge_cases():
    storage = MemoryStorage()

    # Test with None values (should raise ValidationError)
    with pytest.raises(ValidationError):
        storage.save_payment_plan(None)  # type: ignore

    with pytest.raises(ValidationError):
        storage.save_subscription(None)  # type: ignore

    with pytest.raises(ValidationError):
        storage.save_usage_record(None)  # type: ignore

    with pytest.raises(ValidationError):
        storage.save_transaction(None)  # type: ignore

    # Test with empty strings
    assert storage.get_payment_plan("") is None
    assert storage.get_subscription("") is None
    assert storage.get_user_subscription("") is None
    assert storage.get_transaction("") is None


def test_file_storage_edge_cases():
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FileStorage(temp_dir)

        # Test with None values (should raise ValidationError)
        with pytest.raises(ValidationError):
            storage.save_payment_plan(None)  # type: ignore

        with pytest.raises(ValidationError):
            storage.save_subscription(None)  # type: ignore


def test_subscription_status_handling():
    storage = MemoryStorage()

    # Test different subscription statuses
    sub1 = Subscription(id="sub1", user_id="user1", plan_id="plan1", status="active")
    sub2 = Subscription(id="sub2", user_id="user2", plan_id="plan2", status="active")
    sub3 = Subscription(id="sub3", user_id="user3", plan_id="plan3", status="active")

    storage.save_subscription(sub1)
    storage.save_subscription(sub2)
    storage.save_subscription(sub3)

    retrieved1 = storage.get_subscription("sub1")
    retrieved2 = storage.get_subscription("sub2")
    retrieved3 = storage.get_subscription("sub3")

    assert retrieved1 is not None
    assert retrieved1.status == "active"
    assert retrieved2 is not None
    assert retrieved2.status == "active"
    assert retrieved3 is not None
    assert retrieved3.status == "active"


def test_usage_records_date_filtering():
    storage = MemoryStorage()

    # Create usage records with different dates
    record1 = UsageRecord(id="record1", user_id="user1", feature="feature1", cost=0.5)
    record2 = UsageRecord(id="record2", user_id="user1", feature="feature2", cost=0.3)

    storage.save_usage_record(record1)
    storage.save_usage_record(record2)

    # Test filtering by start date
    start_date = datetime.now(timezone.utc) + timedelta(hours=1)  # Future date
    filtered_records = storage.get_user_usage("user1", start_date=start_date)
    assert len(filtered_records) == 0

    # Test filtering by end date
    end_date = datetime.now(timezone.utc) - timedelta(hours=1)  # Past date
    filtered_records = storage.get_user_usage("user1", end_date=end_date)
    assert len(filtered_records) == 0


def test_file_storage_error_handling_corruption():
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = FileStorage(temp_dir)

        # Test with corrupted JSON file
        plan_file = os.path.join(temp_dir, "payment_plans.json")
        with open(plan_file, "w") as f:
            f.write("invalid json content")

        # Should handle gracefully
        plans = storage.list_payment_plans()
        assert isinstance(plans, list)


def test_database_storage_initialization():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    try:
        storage = DatabaseStorage(db_path)
        assert storage is not None
        assert storage.db_path == db_path

        # Test that tables are created
        plan = PaymentPlan(id="test_plan", name="Test Plan", price=10.0)
        storage.save_payment_plan(plan)

        retrieved = storage.get_payment_plan("test_plan")
        assert retrieved is not None
        assert retrieved.id == "test_plan"
    finally:
        os.unlink(db_path)


def test_database_storage_payment_plans():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    try:
        storage = DatabaseStorage(db_path)

        # Test save and get payment plan
        plan = PaymentPlan(id="test_plan", name="Test Plan", price=10.0)
        storage.save_payment_plan(plan)

        retrieved = storage.get_payment_plan("test_plan")
        assert retrieved is not None
        assert retrieved.id == "test_plan"
        assert retrieved.name == "Test Plan"
        assert retrieved.price == 10.0

        # Test get non-existent plan
        assert storage.get_payment_plan("nonexistent") is None

        # Test list payment plans
        plan2 = PaymentPlan(id="test_plan2", name="Test Plan 2", price=20.0)
        storage.save_payment_plan(plan2)

        plans = storage.list_payment_plans()
        assert len(plans) == 2
    finally:
        os.unlink(db_path)


def test_database_storage_subscriptions():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    try:
        storage = DatabaseStorage(db_path)

        # Test save and get subscription
        sub = Subscription(id="test_sub", user_id="user1", plan_id="test_plan", status="active")
        storage.save_subscription(sub)

        retrieved = storage.get_subscription("test_sub")
        assert retrieved is not None
        assert retrieved.id == "test_sub"
        assert retrieved.user_id == "user1"

        # Test get user subscription
        user_sub = storage.get_user_subscription("user1")
        assert user_sub is not None
        assert user_sub.id == "test_sub"
    finally:
        os.unlink(db_path)


def test_database_storage_usage_records():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    try:
        storage = DatabaseStorage(db_path)

        # Test save usage record
        record = UsageRecord(id="test_record", user_id="user1", feature="test_feature", cost=0.5)
        storage.save_usage_record(record)

        # Test get user usage
        record2 = UsageRecord(id="test_record2", user_id="user1", feature="test_feature2", cost=0.3)
        storage.save_usage_record(record2)

        user_records = storage.get_user_usage("user1")
        assert len(user_records) == 2
    finally:
        os.unlink(db_path)


def test_database_storage_transactions():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    try:
        storage = DatabaseStorage(db_path)

        # Test save and get transaction
        transaction = PaymentTransaction(
            id="test_transaction",
            user_id="user1",
            amount=10.0,
            currency="USD",
            payment_method="stripe",
            status="completed",
        )
        storage.save_transaction(transaction)

        retrieved = storage.get_transaction("test_transaction")
        assert retrieved is not None
        assert retrieved.id == "test_transaction"
        assert retrieved.user_id == "user1"
        assert retrieved.amount == 10.0
    finally:
        os.unlink(db_path)


def test_storage_capabilities():
    # Test MemoryStorage capabilities
    memory_storage = MemoryStorage()
    caps = memory_storage.get_capabilities()
    assert caps.supports_transactions is True
    assert caps.supports_backup is False
    assert caps.supports_search is False

    # Test FileStorage capabilities
    with tempfile.TemporaryDirectory() as temp_dir:
        file_storage = FileStorage(temp_dir)
        caps = file_storage.get_capabilities()
        assert caps.supports_backup is True
        assert caps.supports_search is False

    # Test DatabaseStorage capabilities
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name
        try:
            db_storage = DatabaseStorage(db_path)
            caps = db_storage.get_capabilities()
            assert caps.supports_transactions is True
            assert caps.supports_backup is True
            assert caps.supports_search is True
        finally:
            os.unlink(db_path)


def test_storage_health_checks():
    # Test MemoryStorage health check
    memory_storage = MemoryStorage()
    health = memory_storage.check_health()
    assert health.is_healthy is True

    # Test FileStorage health check
    with tempfile.TemporaryDirectory() as temp_dir:
        file_storage = FileStorage(temp_dir)
        health = file_storage.check_health()
        assert health.is_healthy is True

    # Test DatabaseStorage health check
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name
        try:
            db_storage = DatabaseStorage(db_path)
            health = db_storage.check_health()
            assert health.is_healthy is True
        finally:
            os.unlink(db_path)


def test_storage_validation():
    storage = MemoryStorage()

    # Test empty string plan_id (returns None, doesn't raise)
    assert storage.get_payment_plan("") is None

    # Test None plan_id (raises ValidationError)
    with pytest.raises(ValidationError):
        storage.get_payment_plan(None)  # type: ignore

    # Test empty string subscription_id (returns None, doesn't raise)
    assert storage.get_subscription("") is None

    # Test None subscription_id (raises ValidationError)
    with pytest.raises(ValidationError):
        storage.get_subscription(None)  # type: ignore

    # Test empty string transaction_id (returns None, doesn't raise)
    assert storage.get_transaction("") is None

    # Test None transaction_id (raises ValidationError)
    with pytest.raises(ValidationError):
        storage.get_transaction(None)  # type: ignore
