# (No code change needed if relative imports are correct; just move the file.)

import pytest

from aiagent_payments import (
    BillingPeriod,
    PaymentManager,
    PaymentPlan,
    PaymentType,
    UsageLimitExceeded,
)


def test_basic_functionality():
    pm = PaymentManager()
    plan = PaymentPlan(
        id="basic",
        name="Basic Plan",
        description="Basic plan with 5 uses per month",
        payment_type=PaymentType.SUBSCRIPTION,
        price=10.0,
        billing_period=BillingPeriod.MONTHLY,
        requests_per_period=5,
        features=["test_feature"],
    )
    pm.create_payment_plan(plan)
    user_id = "test_user"
    pm.subscribe_user(user_id, "basic")

    @pm.paid_feature(feature_name="test_feature")
    def my_feature(user_id):
        return "ok"

    # Should work 5 times
    for _ in range(5):
        assert my_feature(user_id) == "ok"

    # 6th time should raise UsageLimitExceeded
    with pytest.raises(UsageLimitExceeded):
        my_feature(user_id)
