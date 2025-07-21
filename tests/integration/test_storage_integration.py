from datetime import datetime, timezone

from aiagent_payments.models import (
    BillingPeriod,
    PaymentPlan,
    PaymentType,
    Subscription,
    UsageRecord,
)
from aiagent_payments.storage import DatabaseStorage, FileStorage, MemoryStorage


def make_plan():
    return PaymentPlan(
        id="plan1",
        name="Plan 1",
        payment_type=PaymentType.SUBSCRIPTION,
        price=10.0,
        billing_period=BillingPeriod.MONTHLY,
        requests_per_period=5,
        features=["f1"],
    )


def make_sub():
    now = datetime.now(timezone.utc)
    return Subscription(
        id="sub1",
        user_id="u1",
        plan_id="plan1",
        start_date=now,
        end_date=now,
        usage_count=1,
    )


def make_usage():
    now = datetime.now(timezone.utc)
    return UsageRecord(id="u1", user_id="u1", feature="f1", timestamp=now, cost=1.0)


def test_memory_storage():
    s = MemoryStorage()
    plan = make_plan()
    s.save_payment_plan(plan)
    assert s.get_payment_plan(plan.id).id == plan.id
    sub = make_sub()
    s.save_subscription(sub)
    assert s.get_subscription(sub.id).id == sub.id
    usage = make_usage()
    s.save_usage_record(usage)
    # No assertion, just ensure no error


def test_file_storage(tmp_path):
    tmp_path / "plans.json"
    tmp_path / "subs.json"
    tmp_path / "usage.json"
    s = FileStorage(str(tmp_path))
    plan = make_plan()
    s.save_payment_plan(plan)
    assert s.get_payment_plan(plan.id).id == plan.id
    sub = make_sub()
    s.save_subscription(sub)
    assert s.get_subscription(sub.id).id == sub.id
    usage = make_usage()
    s.save_usage_record(usage)


def test_database_storage(tmp_path):
    db_path = str(tmp_path / "test.db")
    s = DatabaseStorage(db_path)
    plan = make_plan()
    s.save_payment_plan(plan)
    assert s.get_payment_plan(plan.id).id == plan.id
    sub = make_sub()
    s.save_subscription(sub)
    assert s.get_subscription(sub.id).id == sub.id
    usage = make_usage()
    s.save_usage_record(usage)
