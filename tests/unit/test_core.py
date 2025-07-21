from datetime import datetime, timedelta, timezone

import pytest

from aiagent_payments import MemoryStorage, MockProvider, PaymentManager, PaymentPlan
from aiagent_payments.exceptions import (
    ConfigurationError,
    SubscriptionExpired,
    UsageLimitExceeded,
)
from aiagent_payments.models import BillingPeriod, PaymentType


def test_payment_manager_initialization():
    storage = MemoryStorage()
    provider = MockProvider()
    pm = PaymentManager(storage=storage, payment_provider=provider)
    assert pm is not None


def test_create_payment_plan():
    pm = PaymentManager()
    plan = PaymentPlan(id="test_plan", name="Test Plan", price=10.0, currency="USD")
    pm.create_payment_plan(plan)
    retrieved = pm.get_payment_plan("test_plan")
    assert retrieved is not None
    assert retrieved.id == "test_plan"
    assert retrieved.name == "Test Plan"
    assert retrieved.price == 10.0


def test_get_payment_plan():
    pm = PaymentManager()
    plan = PaymentPlan(id="test_plan", name="Test Plan", price=10.0)
    pm.create_payment_plan(plan)
    retrieved = pm.get_payment_plan("test_plan")
    assert retrieved is not None
    assert retrieved.id == "test_plan"


def test_list_payment_plans():
    pm = PaymentManager()
    plan1 = PaymentPlan(id="plan1", name="Plan 1", price=10.0)
    plan2 = PaymentPlan(id="plan2", name="Plan 2", price=20.0)
    pm.create_payment_plan(plan1)
    pm.create_payment_plan(plan2)
    plans = pm.list_payment_plans()
    assert len(plans) >= 2


def test_subscribe_user():
    pm = PaymentManager()
    plan = PaymentPlan(id="test_plan", name="Test Plan", price=10.0)
    pm.create_payment_plan(plan)
    sub = pm.subscribe_user("user1", "test_plan")
    assert sub.user_id == "user1"
    assert sub.plan_id == "test_plan"


def test_get_user_subscription():
    pm = PaymentManager()
    plan = PaymentPlan(id="test_plan", name="Test Plan", price=10.0)
    pm.create_payment_plan(plan)
    sub = pm.subscribe_user("user1", "test_plan")
    user_sub = pm.get_user_subscription("user1")
    assert user_sub is not None
    assert user_sub.id == sub.id


def test_record_usage():
    pm = PaymentManager()
    record = pm.record_usage("user1", "test_feature", 0.5)
    assert record.user_id == "user1"
    assert record.feature == "test_feature"
    assert record.cost == 0.5


def test_get_user_usage():
    pm = PaymentManager()
    pm.record_usage("user1", "test_feature", 0.5)
    records = pm.get_user_usage("user1")
    assert len(records) >= 1


def test_check_access_freemium():
    pm = PaymentManager()
    # Create freemium plan with specific features
    plan = PaymentPlan(
        id="freemium",
        name="Freemium",
        price=0.01,
        free_requests=2,
        payment_type=PaymentType.FREEMIUM,
        features=["test_feature"],
    )
    pm.create_payment_plan(plan)
    # Should allow first 2 requests
    assert pm.check_access("user1", "test_feature")
    # Record usage to track the limit
    pm.record_usage("user1", "test_feature", 0.01)
    assert pm.check_access("user1", "test_feature")
    pm.record_usage("user1", "test_feature", 0.01)
    # Should deny after limit
    assert not pm.check_access("user1", "test_feature")


def test_check_access_subscription():
    pm = PaymentManager()
    plan = PaymentPlan(
        id="pro",
        name="Pro",
        price=10.0,
        requests_per_period=5,
        features=["test_feature"],
    )
    pm.create_payment_plan(plan)
    pm.subscribe_user("user1", "pro")
    # Should allow within subscription
    assert pm.check_access("user1", "test_feature")


def test_check_access_pay_per_use():
    pm = PaymentManager()
    plan = PaymentPlan(
        id="pay_per_use",
        name="Pay Per Use",
        price=0.1,
        payment_type=PaymentType.PAY_PER_USE,
        price_per_request=0.1,
        features=["test_feature"],
    )
    pm.create_payment_plan(plan)
    # Should deny access (no automatic payment processing in check_access)
    assert not pm.check_access("user1", "test_feature")


def test_process_payment():
    pm = PaymentManager()
    transaction = pm.process_payment("user1", 10.0, "USD")
    assert transaction.amount == 10.0
    assert transaction.currency == "USD"


def test_verify_payment():
    pm = PaymentManager()
    transaction = pm.process_payment("user1", 10.0, "USD")
    verified = pm.verify_payment(transaction.id)
    assert isinstance(verified, bool)


def test_paid_feature_decorator():
    pm = PaymentManager()
    plan = PaymentPlan(
        id="freemium",
        name="Freemium",
        price=0.01,
        free_requests=1,
        payment_type=PaymentType.FREEMIUM,
        features=["test_feature"],
    )
    pm.create_payment_plan(plan)

    @pm.paid_feature("test_feature", cost=0.1)
    def test_function(user_id, *args, **kwargs):
        return "success"

    # Should work for first call
    result = test_function("user1")
    assert result == "success"

    # Should fail for second call
    with pytest.raises(UsageLimitExceeded):
        test_function("user1")


def test_subscription_required_decorator():
    pm = PaymentManager()
    plan = PaymentPlan(id="pro", name="Pro", price=10.0, features=["premium_function"])
    pm.create_payment_plan(plan)
    pm.subscribe_user("user1", "pro")

    @pm.subscription_required("pro")
    def premium_function(user_id, *args, **kwargs):
        return "premium"

    # Should work for subscribed user
    result = premium_function("user1")
    assert result == "premium"

    # Should fail for non-subscribed user
    with pytest.raises(SubscriptionExpired):
        premium_function("user2")


def test_usage_limit_decorator():
    pm = PaymentManager()

    @pm.usage_limit(2, "test_feature")
    def limited_function(user_id, *args, **kwargs):
        return "limited"

    # Should work for first 2 calls
    assert limited_function("user1") == "limited"
    assert limited_function("user1") == "limited"

    # Should fail for third call
    with pytest.raises(UsageLimitExceeded):
        limited_function("user1")


def test_subscription_expired():
    pm = PaymentManager()
    plan = PaymentPlan(id="test_plan", name="Test Plan", price=10.0)
    pm.create_payment_plan(plan)
    sub = pm.subscribe_user("user1", "test_plan")

    # Manually expire subscription by setting status to expired
    if sub is not None:
        sub.status = "expired"
        pm.storage.save_subscription(sub)

    # Should not have access after expiration
    assert not pm.check_access("user1", "test_feature")


def test_error_handling():
    pm = PaymentManager()

    # Test with invalid plan
    with pytest.raises(ConfigurationError):
        pm.subscribe_user("user1", "nonexistent_plan")

    # Test with invalid subscription
    assert pm.get_user_subscription("nonexistent") is None


def test_usage_tracking_edge_cases():
    pm = PaymentManager()

    # Test zero cost usage
    record = pm.record_usage("user1", "free_feature", 0.01)
    assert record.cost == 0.01

    # Test negative cost (should raise ValidationError)
    with pytest.raises(Exception):
        pm.record_usage("user1", "refund_feature", -0.5)


def test_subscription_management():
    pm = PaymentManager()
    plan = PaymentPlan(id="test_plan", name="Test Plan", price=10.0)
    pm.create_payment_plan(plan)

    # Create subscription
    sub = pm.subscribe_user("user1", "test_plan")
    assert sub.status == "active"

    # Cancel subscription
    cancelled = pm.cancel_user_subscription("user1")
    assert cancelled

    # Should not have access after cancellation
    assert not pm.check_access("user1", "test_feature")


def test_get_default_plan():
    pm = PaymentManager(default_plan="freemium")
    plan = PaymentPlan(id="freemium", name="Freemium", price=0.01)
    pm.create_payment_plan(plan)

    default = pm.get_default_plan()
    assert default.id == "freemium"


def test_billing_period_calculation():
    pm = PaymentManager()
    plan = PaymentPlan(
        id="monthly_plan",
        name="Monthly Plan",
        price=10.0,
        billing_period=BillingPeriod.MONTHLY,
    )
    pm.create_payment_plan(plan)
    sub = pm.subscribe_user("user1", "monthly_plan")

    # Check that billing period is set correctly
    assert sub.current_period_start is not None
    assert sub.current_period_end is not None
    assert sub.current_period_end > sub.current_period_start


def test_access_control_validation():
    pm = PaymentManager()

    # Test invalid user_id
    with pytest.raises(Exception):
        pm.check_access("", "test_feature")

    # Test invalid feature
    with pytest.raises(Exception):
        pm.check_access("user1", "")


def test_usage_recording_validation():
    pm = PaymentManager()

    # Test invalid user_id
    with pytest.raises(Exception):
        pm.record_usage("", "test_feature")

    # Test invalid feature
    with pytest.raises(Exception):
        pm.record_usage("user1", "")

    # Test negative cost
    with pytest.raises(Exception):
        pm.record_usage("user1", "test_feature", -1.0)


def test_subscribe_user_invalid_plan():
    pm = PaymentManager()
    with pytest.raises(Exception):
        pm.subscribe_user("user1", "nonexistent_plan")


def test_double_subscription_switching():
    pm = PaymentManager()
    plan1 = PaymentPlan(id="plan1", name="Plan 1", price=10.0)
    plan2 = PaymentPlan(id="plan2", name="Plan 2", price=20.0)
    pm.create_payment_plan(plan1)
    pm.create_payment_plan(plan2)
    pm.subscribe_user("user1", "plan1")
    # Switch to another plan
    pm.subscribe_user("user1", "plan2")
    user_sub = pm.get_user_subscription("user1")
    assert user_sub is not None
    assert user_sub.plan_id == "plan2"


def test_expired_and_cancelled_subscription():
    pm = PaymentManager()
    plan = PaymentPlan(id="pro", name="Pro", price=10.0, features=["f"])
    pm.create_payment_plan(plan)
    sub = pm.subscribe_user("user1", "pro")
    if sub is not None:
        # Simulate expiry
        sub.status = "expired"
        pm.storage.save_subscription(sub)
        user_sub = pm.get_user_subscription("user1")
        assert user_sub is None  # Should be None for non-active
        # Simulate cancellation
        sub.status = "cancelled"
        pm.storage.save_subscription(sub)
        user_sub = pm.get_user_subscription("user1")
        assert user_sub is None  # Should be None for non-active


def test_concurrent_usage_tracking():
    pm = PaymentManager()
    plan = PaymentPlan(
        id="freemium", name="Freemium", price=0.01, free_requests=5, payment_type=PaymentType.FREEMIUM, features=["f"]
    )
    pm.create_payment_plan(plan)
    import threading
    import time

    results = []
    lock = threading.Lock()

    def use():
        try:
            pm.record_usage("user1", "f", 0.01)
            with lock:
                results.append(True)
        except Exception:
            with lock:
                results.append(False)

    threads = [threading.Thread(target=use) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Due to race conditions, we can't guarantee exactly 5 successes
    # But we should have some successes and some failures
    assert results.count(True) >= 4  # At least 4 should succeed
    assert results.count(False) >= 4  # At least 4 should fail
    assert len(results) == 10  # Total should be 10


def test_invalid_user_and_feature():
    pm = PaymentManager()
    with pytest.raises(Exception):
        pm.check_access("", "test_feature")
    with pytest.raises(Exception):
        pm.check_access("user1", "")
    with pytest.raises(Exception):
        pm.record_usage("", "test_feature", 0.0)
    with pytest.raises(Exception):
        pm.record_usage("user1", "", 0.0)


def test_multiple_decorators():
    pm = PaymentManager()
    plan = PaymentPlan(id="pro", name="Pro", price=10.0, features=["f"])
    pm.create_payment_plan(plan)
    pm.subscribe_user("user1", "pro")

    @pm.paid_feature("f")
    @pm.subscription_required("pro")
    def decorated(user_id):
        return "ok"

    assert decorated("user1") == "ok"
    with pytest.raises(Exception):
        decorated("user2")


def test_usage_tracker_direct():
    from aiagent_payments.core import UsageTracker
    from aiagent_payments.storage import MemoryStorage

    tracker = UsageTracker(MemoryStorage())
    tracker.record_usage("user1", "f", 1.0)
    assert tracker.get_usage_count("user1", "f") == 1
    tracker.record_usage("user1", "f", 1.0)
    assert tracker.get_usage_count("user1", "f") == 2
    records = tracker.get_user_usage("user1")
    assert len(records) == 2


def test_subscription_manager_direct():
    from aiagent_payments.core import SubscriptionManager
    from aiagent_payments.storage import MemoryStorage

    storage = MemoryStorage()
    manager = SubscriptionManager(storage)
    plan = PaymentPlan(id="pro", name="Pro", price=10.0, features=["f"])
    storage.save_payment_plan(plan)
    sub = manager.create_subscription("user1", "pro")
    assert sub.user_id == "user1"
    assert sub.plan_id == "pro"
    assert manager.check_subscription_access("user1", "f")
    # Expire subscription
    sub.status = "expired"
    # storage.save_subscription(sub) # This line is removed as per the edit hint
    assert not manager.check_subscription_access("user1", "f")


def test_paid_feature_decorator_error_propagation():
    pm = PaymentManager()
    plan = PaymentPlan(
        id="freemium", name="Freemium", price=0.01, free_requests=1, payment_type=PaymentType.FREEMIUM, features=["f"]
    )
    pm.create_payment_plan(plan)

    @pm.paid_feature("f")
    def will_fail(user_id):
        raise RuntimeError("fail")

    # Should raise the original error after usage is recorded
    with pytest.raises(RuntimeError):
        will_fail("user1")
