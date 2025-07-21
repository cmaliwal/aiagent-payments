"""
Basic usage example for AI Agent Payments SDK.
"""

from aiagent_payments import MemoryStorage, PaymentManager, PaymentPlan
from aiagent_payments.models import BillingPeriod, PaymentType
from aiagent_payments.providers import create_payment_provider


def main():
    """Demonstrate basic SDK functionality."""

    print("🚀 AI Agent Payments SDK - Basic Usage Example")
    print("=" * 50)

    # Initialize payment manager with memory storage and mock provider
    storage = MemoryStorage()
    payment_provider = create_payment_provider("mock")
    pm = PaymentManager(storage=storage, payment_provider=payment_provider)

    # Create payment plans
    print("\n📋 Creating payment plans...")

    # Freemium plan
    freemium_plan = PaymentPlan(
        id="freemium",
        name="Freemium",
        description="Free tier with limited usage",
        payment_type=PaymentType.FREEMIUM,
        price=0.0,
        free_requests=5,
        features=["basic_ai_response", "simple_analysis"],
    )

    # Pro subscription plan
    pro_plan = PaymentPlan(
        id="pro",
        name="Pro Subscription",
        description="Professional subscription with unlimited usage",
        payment_type=PaymentType.SUBSCRIPTION,
        price=29.99,
        billing_period=BillingPeriod.MONTHLY,
        requests_per_period=1000,
        features=["advanced_ai_response", "complex_analysis", "priority_support"],
    )

    # Pay-per-use plan
    pay_per_use_plan = PaymentPlan(
        id="pay_per_use",
        name="Pay per Use",
        description="Pay only for what you use",
        payment_type=PaymentType.PAY_PER_USE,
        price=0.01,  # Minimum price required by validation
        price_per_request=0.01,
        features=["all_features"],
    )

    # Add plans to payment manager
    pm.create_payment_plan(freemium_plan)
    pm.create_payment_plan(pro_plan)
    pm.create_payment_plan(pay_per_use_plan)

    print("✅ Payment plans created successfully!")

    # Define AI functions with payment decorators
    print("\n🤖 Setting up AI functions with payment controls...")

    @pm.paid_feature(feature_name="basic_ai_response", cost=0.01)
    def basic_ai_response(user_id: str, prompt: str):
        """Basic AI response function."""
        return f"Basic AI response to: {prompt}"

    @pm.paid_feature(feature_name="advanced_ai_response", cost=0.05)
    def advanced_ai_response(user_id: str, prompt: str):
        """Advanced AI response function."""
        return f"Advanced AI response to: {prompt} (with enhanced processing)"

    @pm.subscription_required(plan_id="pro")
    def complex_analysis(user_id: str, data: str):
        """Complex analysis function (subscription only)."""
        return f"Complex analysis of: {data} (Pro feature)"

    @pm.usage_limit(max_uses=3, feature_name="premium_feature")
    def premium_feature(user_id: str, input_data: str):
        """Premium feature with usage limit."""
        return f"Premium feature result for: {input_data}"

    print("✅ AI functions configured with payment controls!")

    # Test with different users
    print("\n👥 Testing with different users...")

    # User 1: Freemium user
    user1 = "user_freemium"
    print(f"\n--- Testing {user1} (Freemium) ---")

    try:
        # Should work (within free limit)
        for i in range(3):
            result = basic_ai_response(user1, f"Test prompt {i + 1}")
            print(f"  ✅ Basic AI response {i + 1}: {result}")

        # Should fail (exceeded free limit)
        result = basic_ai_response(user1, "Test prompt 6")
        print(f"  ❌ This should fail: {result}")
    except Exception as e:
        print(f"  ❌ Expected error: {e}")

    # User 2: Pro subscription user
    user2 = "user_pro"
    print(f"\n--- Testing {user2} (Pro Subscription) ---")

    try:
        # Subscribe user to pro plan
        subscription = pm.subscribe_user(user2, "pro")
        print(f"  ✅ Subscribed to Pro plan: {subscription.id}")

        # Should work (subscription feature)
        result = complex_analysis(user2, "Test data")
        print(f"  ✅ Complex analysis: {result}")

        # Should work (advanced feature)
        result = advanced_ai_response(user2, "Advanced prompt")
        print(f"  ✅ Advanced AI response: {result}")

    except Exception as e:
        print(f"  ❌ Error: {e}")

    # User 3: Pay-per-use user
    user3 = "user_pay_per_use"
    print(f"\n--- Testing {user3} (Pay per Use) ---")

    try:
        # Should work (pay-per-use)
        result = advanced_ai_response(user3, "Pay per use prompt")
        print(f"  ✅ Pay-per-use response: {result}")

    except Exception as e:
        print(f"  ❌ Error: {e}")

    # User 4: Usage limit testing
    user4 = "user_limited"
    print(f"\n--- Testing {user4} (Usage Limited Feature) ---")

    try:
        # Should work (within limit)
        for i in range(3):
            result = premium_feature(user4, f"Premium data {i + 1}")
            print(f"  ✅ Premium feature {i + 1}: {result}")

        # Should fail (exceeded limit)
        result = premium_feature(user4, "Premium data 4")
        print(f"  ❌ This should fail: {result}")
    except Exception as e:
        print(f"  ❌ Expected error: {e}")

    # Show usage statistics
    print("\n📊 Usage Statistics:")
    print("=" * 30)

    for user_id in [user1, user2, user3, user4]:
        usage_records = pm.get_user_usage(user_id)
        total_cost = sum(r.cost or 0 for r in usage_records)

        print(f"\n{user_id}:")
        print(f"  Total usage: {len(usage_records)} records")
        print(f"  Total cost: ${total_cost:.2f}")

        # Group by feature
        feature_usage = {}
        for record in usage_records:
            feature = record.feature
            feature_usage[feature] = feature_usage.get(feature, 0) + 1

        for feature, count in feature_usage.items():
            print(f"  {feature}: {count} uses")

    # Show subscription status
    print("\n🔍 Subscription Status:")
    print("=" * 25)

    for user_id in [user1, user2, user3, user4]:
        subscription = pm.get_user_subscription(user_id)
        if subscription:
            plan = pm.get_payment_plan(subscription.plan_id)
            print(f"{user_id}: {plan.name if plan else subscription.plan_id} ({subscription.status})")
        else:
            print(f"{user_id}: No subscription")

    print("\n🎉 Example completed successfully!")
    print("\nThis demonstrates:")
    print("- Freemium model with usage limits")
    print("- Subscription-based access control")
    print("- Pay-per-use billing")
    print("- Usage tracking and analytics")
    print("- Decorator-based payment integration")


if __name__ == "__main__":
    main()
