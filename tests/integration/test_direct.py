# (No code change needed if relative imports are correct; just move the file.)


from aiagent_payments import (
    PaymentManager,
    PaymentPlan,
    PaymentType,
)


def test_basic_functionality():
    pm = PaymentManager()
    plan = PaymentPlan(
        id="payg",
        name="Pay As You Go",
        description="Pay per use plan",
        payment_type=PaymentType.PAY_PER_USE,
        price=0.01,  # Updated from 0.0 to 0.01 to pass validation
        price_per_request=2.0,
        features=["test_feature"],
    )
    pm.create_payment_plan(plan)
    user_id = "payg_user"
    pm.subscribe_user(user_id, "payg")

    @pm.paid_feature(feature_name="test_feature")
    def my_feature(user_id):
        return "ok"

    # Should work (pay-per-use, no quota)
    for _ in range(3):
        assert my_feature(user_id) == "ok"
