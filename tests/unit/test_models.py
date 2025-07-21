from datetime import datetime, timedelta, timezone

import pytest

from aiagent_payments.exceptions import ValidationError
from aiagent_payments.models import (
    BillingPeriod,
    PaymentPlan,
    PaymentTransaction,
    PaymentType,
    Subscription,
    UsageRecord,
)


def test_payment_plan_methods():
    plan = PaymentPlan(
        id="test",
        name="Test Plan",
        payment_type=PaymentType.SUBSCRIPTION,
        price=10.0,
        billing_period=BillingPeriod.MONTHLY,
        requests_per_period=5,
        features=["f1"],
    )
    assert plan.is_subscription()
    assert not plan.is_freemium()
    assert not plan.is_pay_per_use()
    d = plan.to_dict()
    assert d["payment_type"] == "subscription"
    assert d["billing_period"] == "monthly"


def test_subscription_methods():
    now = datetime.now(timezone.utc)
    sub = Subscription(
        id="sub1",
        user_id="u1",
        plan_id="p1",
        status="active",
        start_date=now,
        end_date=now + timedelta(days=10),
        current_period_start=now,
        current_period_end=now + timedelta(days=10),
        usage_count=2,
    )
    assert sub.is_active()
    assert not sub.is_expired()
    assert sub.get_days_remaining() in (9, 10)
    d = sub.to_dict()
    assert "start_date" in d and "end_date" in d


def test_usage_record_methods():
    now = datetime.now(timezone.utc)
    rec = UsageRecord(id="u1", user_id="u1", feature="f1", timestamp=now, cost=2.0, currency="USD")
    assert rec.get_cost_display() == "2.00 USD"
    assert not rec.is_free()
    d = rec.to_dict()
    assert d["timestamp"] == now.isoformat()


def test_payment_transaction_methods():
    now = datetime.now(timezone.utc)
    tx = PaymentTransaction(
        id="t1",
        user_id="u1",
        amount=5.0,
        currency="USD",
        payment_method="mock",
        status="pending",
        created_at=now,
    )
    assert tx.is_pending()
    tx.mark_completed()
    assert tx.is_completed()
    assert tx.get_amount_display() == "5.00 USD"
    d = tx.to_dict()
    assert d["created_at"] == now.isoformat()


def test_currency_code_accepts_usdt():
    now = datetime.now(timezone.utc)
    # PaymentPlan with USDT
    plan = PaymentPlan(
        id="plan_usdt",
        name="USDT Plan",
        payment_type=PaymentType.PAY_PER_USE,
        price=1.0,
        currency="USDT",
    )
    assert plan.currency == "USDT"

    # UsageRecord with USDT
    rec = UsageRecord(id="rec_usdt", user_id="u1", feature="f1", cost=1.0, currency="USDT")
    assert rec.currency == "USDT"

    # PaymentTransaction with USDT
    tx = PaymentTransaction(
        id="tx_usdt",
        user_id="u1",
        amount=2.0,
        currency="USDT",
        payment_method="crypto_usdt",
        status="pending",
        created_at=now,
    )
    assert tx.currency == "USDT"


def test_currency_code_rejects_invalid():
    now = datetime.now(timezone.utc)
    # Too long
    with pytest.raises(ValidationError):
        PaymentPlan(
            id="plan_bad",
            name="Bad Plan",
            payment_type=PaymentType.PAY_PER_USE,
            price=1.0,
            currency="USDTX",
        )
    # Too short
    with pytest.raises(ValidationError):
        UsageRecord(id="rec_bad", user_id="u1", feature="f1", cost=1.0, currency="US")
    # Too long for PaymentTransaction
    with pytest.raises(ValidationError):
        PaymentTransaction(
            id="tx_bad",
            user_id="u1",
            amount=2.0,
            currency="USDTX",
            payment_method="crypto_usdt",
            status="pending",
            created_at=now,
        )
