from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest

from aiagent_payments.core import SubscriptionManager, UsageTracker
from aiagent_payments.exceptions import ConfigurationError, ValidationError
from aiagent_payments.models import BillingPeriod, PaymentPlan
from aiagent_payments.storage import MemoryStorage


def test_usage_tracker_record_and_get():
    storage = MemoryStorage()
    tracker = UsageTracker(storage)
    record = tracker.record_usage("user1", "feature1", 1.5, {"meta": 1})
    assert record.user_id == "user1"
    assert record.feature == "feature1"
    assert record.cost == 1.5
    records = tracker.get_user_usage("user1")
    assert len(records) == 1
    assert records[0].feature == "feature1"


def test_usage_tracker_count_and_total():
    storage = MemoryStorage()
    tracker = UsageTracker(storage)
    tracker.record_usage("user1", "f", 2.0)
    tracker.record_usage("user1", "f", 3.0)
    tracker.record_usage("user1", "g", 1.0)
    assert tracker.get_usage_count("user1", "f") == 2
    assert tracker.get_total_cost("user1") == 6.0


def test_usage_tracker_validation():
    storage = MemoryStorage()
    tracker = UsageTracker(storage)
    with pytest.raises(ValidationError):
        tracker.record_usage("user1", "", 1.0)
    with pytest.raises(ValidationError):
        tracker.record_usage("user1", "f", 1.0, metadata=cast(Any, "notadict"))


def test_subscription_manager_create_and_get():
    storage = MemoryStorage()
    plan = PaymentPlan(id="p1", name="P1", price=10.0, billing_period=BillingPeriod.MONTHLY)
    storage.save_payment_plan(plan)
    manager = SubscriptionManager(storage)
    sub = manager.create_subscription("user1", "p1")
    assert sub is not None
    assert sub.user_id == "user1"
    assert sub.plan_id == "p1"
    got = manager.get_user_subscription("user1")
    assert got is not None
    assert got.id == sub.id


def test_subscription_manager_cancel_and_renew():
    storage = MemoryStorage()
    plan = PaymentPlan(id="p1", name="P1", price=10.0, billing_period=BillingPeriod.MONTHLY)
    storage.save_payment_plan(plan)
    manager = SubscriptionManager(storage)
    manager.create_subscription("user1", "p1")
    assert manager.cancel_subscription("user1")
    assert not manager.cancel_subscription("user2")
    # Renew after cancel
    manager.create_subscription("user1", "p1")
    renewed = manager.renew_subscription("user1")
    assert renewed is not None
    assert renewed.status == "active"


def test_subscription_manager_access_and_errors():
    storage = MemoryStorage()
    plan = PaymentPlan(id="p1", name="P1", price=10.0, billing_period=BillingPeriod.MONTHLY, features=["f1"])
    storage.save_payment_plan(plan)
    manager = SubscriptionManager(storage)
    manager.create_subscription("user1", "p1")
    assert manager.check_subscription_access("user1", "f1")
    assert not manager.check_subscription_access("user1", "f2")
    assert not manager.check_subscription_access("user2", "f1")
    # Error on missing plan
    with pytest.raises(ConfigurationError):
        manager.create_subscription("user1", "missing")
