#!/usr/bin/env python3
"""
Usage-Based Billing Example (Real & Simulation Mode)

This example demonstrates usage-based billing with an option to use real payment APIs or fast simulation.

- By default, runs in simulation mode (no real API calls, fast for demos/tests).
- Set USE_REAL_API=1 in your environment to use real payment APIs (Stripe/PayPal).
- For most users, use the fast version: usage_based_billing_fast.py

Key Features:
- Track usage events and costs
- Aggregate usage for billing periods
- Process payments when thresholds are reached
- Handle different billing models (pay-per-use, freemium)
- Usage analytics and reporting
"""

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from aiagent_payments.exceptions import PaymentFailed, ValidationError
from aiagent_payments.models import PaymentTransaction, UsageRecord
from aiagent_payments.providers.paypal import PayPalProvider
from aiagent_payments.providers.stripe import StripeProvider

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USE_REAL_API = os.getenv("USE_REAL_API", "0") == "1"


@dataclass
class BillingThreshold:
    amount: float
    currency: str = "USD"
    billing_period_days: int = 30
    free_usage_limit: int = 0
    price_per_unit: float = 0.01


@dataclass
class UserUsage:
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


class UsageBasedBilling:
    def __init__(self, provider_name: str = "stripe"):
        self.provider_name = provider_name
        self.provider = self._setup_provider() if USE_REAL_API else None
        self.user_usage: Dict[str, UserUsage] = {}
        self.billing_thresholds: Dict[str, BillingThreshold] = {}
        self.billing_history: List[Dict[str, Any]] = []

    def _setup_provider(self):
        if self.provider_name == "stripe" and os.getenv("STRIPE_API_KEY"):
            return StripeProvider()
        elif self.provider_name == "paypal" and os.getenv("PAYPAL_CLIENT_ID"):
            return PayPalProvider(sandbox=True)
        else:
            logger.warning(f"⚠️ {self.provider_name} provider not available, using mock mode")
            return None

    def set_billing_threshold(self, feature: str, threshold: BillingThreshold):
        self.billing_thresholds[feature] = threshold
        logger.info(f"📊 Set billing threshold for {feature}: {threshold.price_per_unit} {threshold.currency} per unit")

    def track_usage(self, user_id: str, feature: str, metadata: Optional[Dict[str, Any]] = None) -> UsageRecord:
        usage_record = UsageRecord(
            id=str(uuid.uuid4()), user_id=user_id, feature=feature, timestamp=datetime.now(timezone.utc), metadata=metadata or {}
        )
        threshold = self.billing_thresholds.get(feature)
        if threshold:
            usage_record.cost = threshold.price_per_unit
            usage_record.currency = threshold.currency
        self._update_user_usage(user_id, feature, usage_record)
        self._check_billing_threshold(user_id, feature)
        return usage_record

    def _update_user_usage(self, user_id: str, feature: str, usage_record: UsageRecord):
        if user_id not in self.user_usage:
            threshold = self.billing_thresholds.get(feature)
            period_days = threshold.billing_period_days if threshold else 30
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
        if user_usage.metadata is None:
            user_usage.metadata = {}
        if "usage_records" not in user_usage.metadata:
            user_usage.metadata["usage_records"] = []
        user_usage.metadata["usage_records"].append(usage_record.to_dict())

    def _check_billing_threshold(self, user_id: str, feature: str):
        user_usage = self.user_usage.get(user_id)
        threshold = self.billing_thresholds.get(feature)
        if not user_usage or not threshold:
            return
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
            self._process_billing(user_id, feature, user_usage, threshold)

    def _process_billing(self, user_id: str, feature: str, user_usage: UserUsage, threshold: BillingThreshold):
        try:
            billable_usage = max(0, user_usage.usage_count - threshold.free_usage_limit)
            billable_amount = billable_usage * threshold.price_per_unit
            if billable_amount <= 0:
                logger.info(
                    f"ℹ️ No billable amount for {user_id} (usage: {user_usage.usage_count}, free limit: {threshold.free_usage_limit})"
                )
                return
            logger.info(f"💳 Processing billing for {user_id}: {billable_amount} {threshold.currency}")
            if self.provider:
                transaction = self.provider.process_payment(
                    user_id=user_id,
                    amount=billable_amount,
                    currency=threshold.currency,
                    metadata={
                        "billing_type": "usage_based",
                        "feature": feature,
                        "usage_count": user_usage.usage_count,
                        "billable_usage": billable_usage,
                        "price_per_unit": threshold.price_per_unit,
                        "billing_period_start": user_usage.current_period_start.isoformat(),
                        "billing_period_end": user_usage.current_period_end.isoformat(),
                    },
                )
                logger.info(f"✅ Billing successful: {transaction.id} for {user_id}")
                self.billing_history.append(
                    {
                        "transaction_id": transaction.id,
                        "user_id": user_id,
                        "feature": feature,
                        "amount": billable_amount,
                        "currency": threshold.currency,
                        "usage_count": user_usage.usage_count,
                        "billable_usage": billable_usage,
                        "billed_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            else:
                # Simulate billing
                transaction_id = str(uuid.uuid4())
                logger.info(f"✅ Billing successful (simulated): {transaction_id} for {user_id}")
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
            user_usage.last_billed = datetime.now(timezone.utc)
            user_usage.usage_count = 0
            user_usage.total_cost = 0.0
            user_usage.current_period_start = datetime.now(timezone.utc)
            user_usage.current_period_end = user_usage.current_period_start + timedelta(days=threshold.billing_period_days)
        except PaymentFailed as e:
            logger.error(f"❌ Billing failed for {user_id}: {e}")
        except Exception as e:
            logger.error(f"💥 Unexpected billing error for {user_id}: {e}")

    def get_user_usage(self, user_id: str) -> Optional[UserUsage]:
        return self.user_usage.get(user_id)

    def get_usage_summary(self) -> Dict[str, Any]:
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
        return self.billing_history


def main():
    print("🚀 Usage-Based Billing Example (Real & Simulation Mode)")
    print("=" * 55)
    print(f"Simulation mode: {'OFF (real API calls)' if USE_REAL_API else 'ON (fast, no API calls)'}")
    billing = UsageBasedBilling(provider_name="stripe")
    billing.set_billing_threshold(
        "api_call",
        BillingThreshold(
            amount=10.00,
            currency="USD",
            billing_period_days=30,
            free_usage_limit=10,  # First 10 calls free (reduced for demo)
            price_per_unit=0.01,
        ),
    )
    billing.set_billing_threshold(
        "image_generation",
        BillingThreshold(
            amount=5.00,
            currency="USD",
            billing_period_days=30,
            free_usage_limit=5,  # First 5 images free (reduced for demo)
            price_per_unit=0.10,
        ),
    )
    billing.set_billing_threshold(
        "text_analysis",
        BillingThreshold(
            amount=15.00,
            currency="USD",
            billing_period_days=30,
            free_usage_limit=5,  # First 5 analyses free (reduced for demo)
            price_per_unit=0.02,
        ),
    )
    users = ["user_001", "user_002", "user_003"]
    print(f"\n📊 Simulating usage for {len(users)} users...")
    for i, user_id in enumerate(users):
        print(f"\n--- User {user_id} ---")
        # Simulate different usage patterns (small numbers for demo)
        if i == 0:
            usage_counts = {"api_call": 12, "image_generation": 6, "text_analysis": 7}
        elif i == 1:
            usage_counts = {"api_call": 15, "image_generation": 8, "text_analysis": 10}
        else:
            usage_counts = {"api_call": 20, "image_generation": 10, "text_analysis": 12}
        for feature, count in usage_counts.items():
            print(f"  {feature}: {count} uses")
            for _ in range(count):
                billing.track_usage(user_id=user_id, feature=feature, metadata={"simulation": not USE_REAL_API, "batch": i})
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
    print(f"\n💰 Billing History:")
    history = billing.get_billing_history()
    for billing_record in history:
        print(
            f"  {billing_record['transaction_id'][:8]}... - {billing_record['user_id']}: ${billing_record['amount']:.2f} ({billing_record['feature']})"
        )
    print("\n" + "=" * 55)
    print("✅ Usage-Based Billing Example Completed!")
    print("\n💡 Key Benefits:")
    print("   • Fast simulation without API calls (default)")
    print("   • Fair billing based on actual usage")
    print("   • Flexible pricing models")
    print("   • Automatic billing when thresholds reached")
    print("   • Support for free tiers and limits")
    print("\n🔧 Production Considerations:")
    print("   • Set USE_REAL_API=1 to enable real payment processing")
    print("   • Store usage data in persistent database")
    print("   • Implement usage aggregation for efficiency")
    print("   • Add usage analytics and reporting")
    print("   • Handle billing failures and retries")
    print("   • Implement usage quotas and rate limiting")


if __name__ == "__main__":
    main()
