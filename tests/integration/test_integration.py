# (No code change needed if relative imports are correct; just move the file.)

import pytest

from aiagent_payments import (
    BillingPeriod,
    PaymentManager,
    PaymentPlan,
    PaymentType,
    UsageLimitExceeded,
)


def test_subscription_and_usage_flow():
    pm = PaymentManager()
    plan = PaymentPlan(
        id="test_sub",
        name="Test Subscription",
        description="Test plan with 2 uses per month",
        payment_type=PaymentType.SUBSCRIPTION,
        price=5.0,
        billing_period=BillingPeriod.MONTHLY,
        requests_per_period=2,
        features=["test_feature"],
    )
    pm.create_payment_plan(plan)
    user_id = "integration_user"
    pm.subscribe_user(user_id, "test_sub")

    @pm.paid_feature(feature_name="test_feature")
    def my_feature(user_id):
        return "ok"

    assert my_feature(user_id) == "ok"
    assert my_feature(user_id) == "ok"
    with pytest.raises(UsageLimitExceeded):
        my_feature(user_id)


def test_pay_per_use_flow():
    pm = PaymentManager()
    plan = PaymentPlan(
        id="test_payg",
        name="Test Pay As You Go",
        description="Pay per use plan",
        payment_type=PaymentType.PAY_PER_USE,
        price=0.01,  # Updated from 0.0 to 0.01 to pass validation
        price_per_request=1.0,
        features=["test_feature"],
    )
    pm.create_payment_plan(plan)
    user_id = "payg_integration_user"
    pm.subscribe_user(user_id, "test_payg")

    @pm.paid_feature(feature_name="test_feature")
    def my_feature(user_id):
        return "ok"

    for _ in range(5):
        assert my_feature(user_id) == "ok"
