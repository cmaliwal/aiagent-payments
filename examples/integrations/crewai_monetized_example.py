"""
Example: Monetized Content Generation Workflow (Simplified)

This example demonstrates how to integrate the AI Agent Payments SDK with a content generation workflow.
A user can generate up to 5 blog posts per month with a subscription plan. The SDK enforces access control and payment.

Real-world use case: SaaS platform offering AI-generated blog posts, charging users per post or via subscription.
"""

import logging
from typing import Any, Dict

from aiagent_payments import (
    BillingPeriod,
    PaymentManager,
    PaymentPlan,
    PaymentRequired,
    PaymentType,
    UsageLimitExceeded,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# flake8: noqa: E226
# --- Setup PaymentManager and Plans ---
pm = PaymentManager()

# Create a subscription plan for blog generation
blog_plan = PaymentPlan(
    id="blogger_pro",
    name="Blogger Pro",
    description="Generate up to 5 blog posts per month",
    payment_type=PaymentType.SUBSCRIPTION,
    price=10.0,
    billing_period=BillingPeriod.MONTHLY,
    requests_per_period=5,
    features=["generate_blog_post"],
)
pm.create_payment_plan(blog_plan)

# Create a pay-per-use plan
pay_per_use_plan = PaymentPlan(
    id="pay_per_post",
    name="Pay Per Post",
    description="Pay $2.00 per blog post",
    payment_type=PaymentType.PAY_PER_USE,
    price=2.0,
    features=["generate_blog_post"],
)
pm.create_payment_plan(pay_per_use_plan)


# --- Simulate a content generation workflow ---
class ContentGenerationWorkflow:
    """Simulates a CrewAI-like workflow for content generation."""

    def __init__(self):
        self.research_data = {}
        self.content_templates = {
            "healthcare": "AI in healthcare is revolutionizing patient care through...",
            "technology": "The latest technology trends are transforming industries...",
            "business": "Modern business strategies are leveraging AI to...",
        }

    def research_topic(self, topic: str) -> Dict[str, Any]:
        """Simulate research phase."""
        logger.info(f"🔍 Researching topic: {topic}")
        # Simulate research time
        import time

        time.sleep(0.1)

        category = topic.lower().split()[0] if topic else "general"
        return {
            "topic": topic,
            "category": category,
            "key_points": [f"Key point 1 about {topic}", f"Key point 2 about {topic}"],
            "sources": ["source1.com", "source2.com"],
            "research_time": "2 minutes",
        }

    def write_content(self, research_data: Dict[str, Any]) -> str:
        """Simulate content writing phase."""
        logger.info(f"✍️ Writing content for: {research_data['topic']}")
        # Simulate writing time
        import time

        time.sleep(0.1)

        category = research_data.get("category", "general")
        template = self.content_templates.get(category, "This is a comprehensive article about...")

        return f"""
# {research_data['topic']}

{template}

## Key Points:
{chr(10).join(f"- {point}" for point in research_data['key_points'])}

## Sources:
{chr(10).join(f"- {source}" for source in research_data['sources'])}

*Generated in {research_data['research_time']}*
        """.strip()


# --- Decorate the workflow with payment control ---
@pm.paid_feature(feature_name="generate_blog_post", cost=2.0, plan_id="blogger_pro")
def generate_blog_post(user_id: str, topic: str) -> str:
    """Generate a blog post using the content workflow."""
    logger.info(f"🚀 Starting blog post generation for user {user_id}")

    # Initialize the workflow
    workflow = ContentGenerationWorkflow()

    # Phase 1: Research
    research_data = workflow.research_topic(topic)

    # Phase 2: Write content
    content = workflow.write_content(research_data)

    logger.info(f"✅ Blog post generated successfully for user {user_id}")
    return content


# --- Simulate different user scenarios ---
def demonstrate_subscription_user():
    """Demonstrate a user with a subscription plan."""
    print("\n" + "=" * 60)
    print("📋 SUBSCRIPTION USER DEMONSTRATION")
    print("=" * 60)

    user_id = "subscriber_001"
    topic = "The Future of AI in Healthcare"

    try:
        # Subscribe the user to the monthly plan
        pm.subscribe_user(user_id, "blogger_pro")
        print(f"✅ User {user_id} subscribed to Blogger Pro plan")

        # Generate multiple blog posts
        for i in range(6):  # Try to generate 6 posts (should fail on the 6th)
            try:
                result = generate_blog_post(user_id, f"{topic} - Part {i+1}")
                print(f"📝 Post {i+1} generated successfully")
                print(f"   Preview: {result[:100]}...")
            except UsageLimitExceeded as e:
                print(f"❌ Post {i+1} failed: {e}")
                break

    except Exception as e:
        print(f"❌ Error: {e}")


def demonstrate_pay_per_use_user():
    """Demonstrate a pay-per-use user."""
    print("\n" + "=" * 60)
    print("💰 PAY-PER-USE USER DEMONSTRATION")
    print("=" * 60)

    user_id = "pay_user_001"
    topic = "Modern Technology Trends"

    try:
        # Generate a blog post (should require payment)
        result = generate_blog_post(user_id, topic)
        print(f"📝 Blog post generated successfully")
        print(f"   Preview: {result[:100]}...")

    except PaymentRequired as e:
        print(f"💳 Payment required: {e}")
        print("   User would be redirected to payment page")
    except Exception as e:
        print(f"❌ Error: {e}")


def demonstrate_usage_tracking():
    """Demonstrate usage tracking and analytics."""
    print("\n" + "=" * 60)
    print("📊 USAGE TRACKING DEMONSTRATION")
    print("=" * 60)

    user_id = "analytics_user_001"

    try:
        # Subscribe user
        pm.subscribe_user(user_id, "blogger_pro")

        # Generate some content
        generate_blog_post(user_id, "AI in Business")
        generate_blog_post(user_id, "Machine Learning Basics")

        # Get usage statistics
        usage_records = pm.get_user_usage(user_id)
        subscription = pm.get_user_subscription(user_id)

        print(f"📈 User {user_id} usage statistics:")
        print(f"   Total usage records: {len(usage_records)}")
        print(f"   Active subscription: {subscription.plan_id if subscription else 'None'}")
        print(f"   Usage count: {subscription.usage_count if subscription else 0}")

        # Fix E226: missing whitespace around arithmetic operator and ensure plan is defined
        if subscription is not None and hasattr(subscription, "usage_count") and hasattr(subscription, "plan_id"):
            # Find the plan by plan_id
            plan = next((p for p in pm.list_payment_plans() if p.id == subscription.plan_id), None)
            if plan and hasattr(plan, "free_requests"):
                # Explicitly add whitespace around arithmetic operators and break up lines
                remaining_quota = plan.free_requests - subscription.usage_count  # noqa: E226
                over_quota = subscription.usage_count - plan.free_requests  # noqa: E226
                total_cost = subscription.usage_count * 0.50  # noqa: E226
                print("  - Remaining quota:", remaining_quota)
                print("  - Over quota by:", over_quota)
                print("  - Total cost:", total_cost)
            else:
                print("  - Plan not found or missing free_requests attribute.")
        else:
            print("  - No subscription or missing attributes for quota/cost calculation.")

    except Exception as e:
        print(f"❌ Error: {e}")


# --- Main execution ---
if __name__ == "__main__":
    print("🚀 Monetized Content Generation Workflow Example")
    print("=" * 60)

    # Demonstrate different user scenarios
    demonstrate_subscription_user()
    demonstrate_pay_per_use_user()
    demonstrate_usage_tracking()

    print("\n" + "=" * 60)
    print("✅ Example completed successfully!")
    print("=" * 60)

    print("\nKey Features Demonstrated:")
    print("• Subscription-based access control")
    print("• Pay-per-use billing")
    print("• Usage tracking and limits")
    print("• Error handling for payment requirements")
    print("• Workflow integration with payment controls")
