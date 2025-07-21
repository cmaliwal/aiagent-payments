#!/usr/bin/env python3
"""
Fast Usage-Based Billing Example (Simulation Mode)

This example demonstrates usage-based billing without making real API calls.
Perfect for testing and demonstration purposes.

Key Features:
- Track usage events and costs
- Simulate billing processing
- Handle different billing models
- Fast execution for testing
"""

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from aiagent_payments.exceptions import ValidationError
from aiagent_payments.models import UsageRecord

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BillingThreshold:
    """Defines billing thresholds for usage-based billing."""

    amount: float
    currency: str = "USD"
    billing_period_days: int = 30
    free_usage_limit: int = 0
    price_per_unit: float = 0.01


@dataclass
class UserUsage:
    """Tracks user usage for billing purposes."""

    user_id: str
    current_period_start: datetime
    current_period_end: datetime
    usage_count: int = 0
    total_cost: float = 0.0
    currency: str = "USD"
    last_billed: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class FastUsageBasedBilling:
    """
    Fast usage-based billing system (simulation mode).

    This class tracks user usage, calculates costs, and simulates billing
    without making real API calls.
    """

    def __init__(self):
        """Initialize the fast usage-based billing system."""
        self.user_usage: Dict[str, UserUsage] = {}
        self.billing_thresholds: Dict[str, BillingThreshold] = {}
        self.billing_history: List[Dict[str, Any]] = []

    def set_billing_threshold(self, feature: str, threshold: BillingThreshold):
        """Set billing threshold for a specific feature."""
        self.billing_thresholds[feature] = threshold
        logger.info(f"📊 Set billing threshold for {feature}: {threshold.price_per_unit} {threshold.currency} per unit")

    def track_usage(self, user_id: str, feature: str, metadata: Optional[Dict[str, Any]] = None) -> UsageRecord:
        """
        Track a usage event for a user.

        Args:
            user_id: Unique identifier for the user
            feature: Feature being used (e.g., 'api_call', 'image_generation')
            metadata: Optional additional metadata

        Returns:
            UsageRecord object
        """
        # Create usage record
        usage_record = UsageRecord(
            id=str(uuid.uuid4()), user_id=user_id, feature=feature, timestamp=datetime.now(timezone.utc), metadata=metadata or {}
        )

        # Calculate cost if threshold exists
        threshold = self.billing_thresholds.get(feature)
        if threshold:
            usage_record.cost = threshold.price_per_unit
            usage_record.currency = threshold.currency

        # Update user usage tracking
        self._update_user_usage(user_id, feature, usage_record)

        # Check if billing threshold reached
        self._check_billing_threshold(user_id, feature)

        return usage_record

    def _update_user_usage(self, user_id: str, feature: str, usage_record: UsageRecord):
        """Update user usage tracking."""
        if user_id not in self.user_usage:
            # Initialize new user usage tracking
            threshold = self.billing_thresholds.get(feature)
            if threshold:
                period_days = threshold.billing_period_days
            else:
                period_days = 30  # Default 30-day period

            now = datetime.now(timezone.utc)
            self.user_usage[user_id] = UserUsage(
                user_id=user_id,
                current_period_start=now,
                current_period_end=now + timedelta(days=period_days),
                currency=usage_record.currency,
            )

        user_usage = self.user_usage[user_id]
        user_usage.usage_count += 1

        if usage_record.cost:
            user_usage.total_cost += usage_record.cost

        # Store usage record in metadata
        if user_usage.metadata is None:
            user_usage.metadata = {}
        if "usage_records" not in user_usage.metadata:
            user_usage.metadata["usage_records"] = []
        user_usage.metadata["usage_records"].append(usage_record.to_dict())

    def _check_billing_threshold(self, user_id: str, feature: str):
        """Check if billing threshold has been reached."""
        user_usage = self.user_usage.get(user_id)
        threshold = self.billing_thresholds.get(feature)

        if not user_usage or not threshold:
            return

        # Check if we should bill based on usage count or cost
        should_bill = False
        billing_reason = ""

        if user_usage.usage_count > threshold.free_usage_limit:
            should_bill = True
            billing_reason = f"Usage count ({user_usage.usage_count}) exceeds free limit ({threshold.free_usage_limit})"
        elif user_usage.total_cost >= threshold.amount:
            should_bill = True
            billing_reason = f"Total cost ({user_usage.total_cost}) reaches threshold ({threshold.amount})"

        if should_bill:
            logger.info(f"💰 Billing threshold reached for {user_id}: {billing_reason}")
            self._simulate_billing(user_id, feature, user_usage, threshold)

    def _simulate_billing(self, user_id: str, feature: str, user_usage: UserUsage, threshold: BillingThreshold):
        """Simulate billing for a user (no real API calls)."""
        try:
            # Calculate billable amount
            billable_usage = max(0, user_usage.usage_count - threshold.free_usage_limit)
            billable_amount = billable_usage * threshold.price_per_unit

            if billable_amount <= 0:
                logger.info(
                    f"ℹ️ No billable amount for {user_id} (usage: {user_usage.usage_count}, free limit: {threshold.free_usage_limit})"
                )
                return

            logger.info(f"💳 Simulating billing for {user_id}: {billable_amount} {threshold.currency}")

            # Simulate successful payment
            transaction_id = str(uuid.uuid4())
            logger.info(f"✅ Billing successful (simulated): {transaction_id} for {user_id}")

            # Record billing history
            self.billing_history.append(
                {
                    "transaction_id": transaction_id,
                    "user_id": user_id,
                    "feature": feature,
                    "amount": billable_amount,
                    "currency": threshold.currency,
                    "usage_count": user_usage.usage_count,
                    "billable_usage": billable_usage,
                    "billed_at": datetime.now(timezone.utc).isoformat(),
                }
            )

            # Update user usage tracking
            user_usage.last_billed = datetime.now(timezone.utc)
            user_usage.usage_count = 0  # Reset for next period
            user_usage.total_cost = 0.0

            # Reset billing period
            user_usage.current_period_start = datetime.now(timezone.utc)
            user_usage.current_period_end = user_usage.current_period_start + timedelta(days=threshold.billing_period_days)

        except Exception as e:
            logger.error(f"💥 Unexpected billing error for {user_id}: {e}")

    def get_user_usage(self, user_id: str) -> Optional[UserUsage]:
        """Get current usage for a user."""
        return self.user_usage.get(user_id)

    def get_usage_summary(self) -> Dict[str, Any]:
        """Get summary of all user usage."""
        summary = {
            "total_users": len(self.user_usage),
            "total_usage_events": sum(u.usage_count for u in self.user_usage.values()),
            "total_cost": sum(u.total_cost for u in self.user_usage.values()),
            "total_billings": len(self.billing_history),
            "users_by_usage": {},
        }

        for user_id, usage in self.user_usage.items():
            summary["users_by_usage"][user_id] = {
                "usage_count": usage.usage_count,
                "total_cost": usage.total_cost,
                "currency": usage.currency,
                "last_billed": usage.last_billed.isoformat() if usage.last_billed else None,
                "period_end": usage.current_period_end.isoformat(),
            }

        return summary

    def get_billing_history(self) -> List[Dict[str, Any]]:
        """Get billing history."""
        return self.billing_history


def main():
    """Demonstrate fast usage-based billing."""
    print("🚀 Fast Usage-Based Billing Example (Simulation Mode)")
    print("=" * 55)

    # Initialize billing system
    billing = FastUsageBasedBilling()

    # Set up billing thresholds for different features
    billing.set_billing_threshold(
        "api_call",
        BillingThreshold(
            amount=10.00,
            currency="USD",
            billing_period_days=30,
            free_usage_limit=1000,  # First 1000 calls free
            price_per_unit=0.01,  # $0.01 per call after free limit
        ),
    )

    billing.set_billing_threshold(
        "image_generation",
        BillingThreshold(
            amount=5.00,
            currency="USD",
            billing_period_days=30,
            free_usage_limit=50,  # First 50 images free
            price_per_unit=0.10,  # $0.10 per image after free limit
        ),
    )

    billing.set_billing_threshold(
        "text_analysis",
        BillingThreshold(
            amount=15.00,
            currency="USD",
            billing_period_days=30,
            free_usage_limit=500,  # First 500 analyses free
            price_per_unit=0.02,  # $0.02 per analysis after free limit
        ),
    )

    # Simulate user usage (reduced counts for faster execution)
    users = ["user_001", "user_002", "user_003"]

    print(f"\n📊 Simulating usage for {len(users)} users...")

    for i, user_id in enumerate(users):
        print(f"\n--- User {user_id} ---")

        # Simulate different usage patterns (reduced for speed)
        if i == 0:  # Light user
            usage_counts = {"api_call": 100, "image_generation": 10, "text_analysis": 50}
        elif i == 1:  # Medium user
            usage_counts = {"api_call": 1200, "image_generation": 60, "text_analysis": 600}
        else:  # Heavy user
            usage_counts = {"api_call": 2500, "image_generation": 120, "text_analysis": 1000}

        for feature, count in usage_counts.items():
            print(f"  {feature}: {count} uses")
            for _ in range(count):
                billing.track_usage(user_id=user_id, feature=feature, metadata={"simulation": True, "batch": i})

    # Show usage summary
    print(f"\n📈 Usage Summary:")
    summary = billing.get_usage_summary()
    print(f"  Total users: {summary['total_users']}")
    print(f"  Total usage events: {summary['total_usage_events']}")
    print(f"  Total cost: ${summary['total_cost']:.2f}")
    print(f"  Total billings: {summary['total_billings']}")

    print(f"\n👥 User Details:")
    for user_id, details in summary["users_by_usage"].items():
        print(f"  {user_id}:")
        print(f"    Usage count: {details['usage_count']}")
        print(f"    Total cost: ${details['total_cost']:.2f}")
        print(f"    Last billed: {details['last_billed'] or 'Never'}")
        print(f"    Period ends: {details['period_end']}")

    # Show billing history
    print(f"\n💰 Billing History:")
    history = billing.get_billing_history()
    for billing_record in history:
        print(
            f"  {billing_record['transaction_id'][:8]}... - {billing_record['user_id']}: ${billing_record['amount']:.2f} ({billing_record['feature']})"
        )

    print("\n" + "=" * 55)
    print("✅ Fast Usage-Based Billing Example Completed!")

    print("\n💡 Key Benefits:")
    print("   • Fast simulation without API calls")
    print("   • Fair billing based on actual usage")
    print("   • Flexible pricing models")
    print("   • Automatic billing when thresholds reached")
    print("   • Support for free tiers and limits")

    print("\n🔧 Production Considerations:")
    print("   • Replace simulation with real payment processing")
    print("   • Store usage data in persistent database")
    print("   • Implement usage aggregation for efficiency")
    print("   • Add usage analytics and reporting")
    print("   • Handle billing failures and retries")
    print("   • Implement usage quotas and rate limiting")


if __name__ == "__main__":
    main()
