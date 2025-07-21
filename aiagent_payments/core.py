"""
Core classes for the AI Agent Payments SDK.

Contains main classes for managing payments, subscriptions, and usage tracking.
"""

import logging
import os
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any

from aiagent_payments.config import ENABLED_STORAGE, is_storage_enabled
from aiagent_payments.storage import MemoryStorage, StorageBackend

from .exceptions import (
    ConfigurationError,
    PaymentFailed,
    PaymentRequired,
    SubscriptionExpired,
    UsageLimitExceeded,
    ValidationError,
)
from .models import (
    BillingPeriod,
    PaymentPlan,
    PaymentTransaction,
    Subscription,
    UsageRecord,
)
from .providers import PaymentProvider, create_payment_provider

logger = logging.getLogger(__name__)


def _create_environment_aware_storage() -> StorageBackend:
    """Create a storage backend based on environment and configuration."""
    # Check if we're in production environment
    is_production = os.getenv("AIAgentPayments_Environment", "").lower() == "production"

    # In production, prioritize persistent storage backends
    if is_production:
        # Try database storage first (most reliable for production)
        if is_storage_enabled("database"):
            try:
                from .storage.database import DatabaseStorage

                logger.info("Initializing DatabaseStorage for production environment")
                return DatabaseStorage()
            except Exception as e:
                logger.warning("Failed to initialize DatabaseStorage: %s", e)

        # Fall back to file storage
        if is_storage_enabled("file"):
            try:
                from .storage.file import FileStorage

                logger.info("Initializing FileStorage for production environment")
                return FileStorage()
            except Exception as e:
                logger.warning("Failed to initialize FileStorage: %s", e)

    # For development/testing or if persistent storage failed, use memory storage
    if is_storage_enabled("memory"):
        logger.info("Initializing MemoryStorage (development/testing environment)")
        return MemoryStorage()

    # Last resort - create memory storage even if not explicitly enabled
    logger.warning("No storage backends available from configuration, using MemoryStorage as fallback")
    return MemoryStorage()


class UsageTracker:
    """Tracks usage for individual users and features."""

    def __init__(self, storage: StorageBackend):
        """Initialize the usage tracker."""
        self.storage = storage
        logger.debug("UsageTracker initialized with storage backend: %s", type(storage).__name__)

    def record_usage(
        self,
        user_id: str,
        feature: str,
        cost: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UsageRecord:
        """Record a usage event for a user and feature."""
        if not feature or not isinstance(feature, str):
            raise ValidationError("Feature name is required and must be a string", field="feature", value=feature)
        if metadata is not None and not isinstance(metadata, dict):
            raise ValidationError("Metadata must be a dictionary if provided", field="metadata", value=metadata)

        record = UsageRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            feature=feature,
            cost=cost,
            metadata=metadata or {},
        )

        self.storage.save_usage_record(record)
        logger.info(f"Recorded usage for user {user_id}, feature {feature}, cost: {cost or 0.0}")
        return record

    def get_user_usage(
        self,
        user_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[UsageRecord]:
        """Get usage records for a user within a date range."""
        records = self.storage.get_user_usage(user_id, start_date, end_date)
        logger.debug(f"Retrieved {len(records):d} usage records for user {user_id}")
        return records

    def get_usage_count(
        self,
        user_id: str,
        feature: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> int:
        """Get the count of usage for a specific feature."""
        records = self.get_user_usage(user_id, start_date, end_date)
        count = len([r for r in records if r.feature == feature])
        logger.debug("Usage count for user %s, feature %s: %d", user_id, feature, count)
        return count

    def get_total_cost(
        self,
        user_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> float:
        """Get total cost for a user within a date range."""
        records = self.get_user_usage(user_id, start_date, end_date)
        total_cost = sum(r.cost or 0 for r in records)
        logger.debug("Total cost for user %s: %.2f", user_id, total_cost)
        return total_cost


class SubscriptionManager:
    """Manages user subscriptions and billing periods."""

    def __init__(self, storage: StorageBackend):
        """Initialize the subscription manager."""
        self.storage = storage
        logger.debug("SubscriptionManager initialized with storage backend: %s", type(storage).__name__)

    def create_subscription(self, user_id: str, plan_id: str, metadata: dict[str, Any] | None = None) -> Subscription:
        """Create a new subscription for a user."""
        plan = self.storage.get_payment_plan(plan_id)
        if not plan:
            logger.error("Payment plan %s not found for user %s", plan_id, user_id)
            raise ConfigurationError(f"Payment plan '{plan_id}' not found for user '{user_id}'")

        # Cancel any existing active subscription
        existing = self.storage.get_user_subscription(user_id)
        if existing:
            existing.status = "cancelled"
            self.storage.save_subscription(existing)
            logger.info("Cancelled existing subscription for user %s", user_id)

        # Calculate billing period dates
        now = datetime.now(timezone.utc)
        current_period_start = now
        current_period_end = None

        if plan.billing_period:
            period_mapping = {
                BillingPeriod.DAILY: timedelta(days=1),
                BillingPeriod.WEEKLY: timedelta(weeks=1),
                BillingPeriod.MONTHLY: timedelta(days=30),
                BillingPeriod.YEARLY: timedelta(days=365),
            }
            billing_period = (
                plan.billing_period if isinstance(plan.billing_period, BillingPeriod) else BillingPeriod(plan.billing_period)
            )
            current_period_end = now + period_mapping.get(billing_period, timedelta(days=30))

        subscription = Subscription(
            id=str(uuid.uuid4()),
            user_id=user_id,
            plan_id=plan_id,
            start_date=now,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            metadata=metadata or {},
        )

        self.storage.save_subscription(subscription)
        logger.info("Created subscription %s for user %s to plan %s", subscription.id, user_id, plan_id)
        return subscription

    def get_user_subscription(self, user_id: str) -> Subscription | None:
        """Get the active subscription for a user."""
        subscription = self.storage.get_user_subscription(user_id)
        if subscription and not subscription.is_active():
            logger.debug("User %s has inactive subscription", user_id)
            return None
        return subscription

    def cancel_subscription(self, user_id: str) -> bool:
        """Cancel a user's subscription."""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            logger.warning("No active subscription found for user %s", user_id)
            return False

        subscription.set_status("cancelled")
        self.storage.save_subscription(subscription)
        logger.info("Cancelled subscription for user %s", user_id)
        return True

    def renew_subscription(self, user_id: str) -> Subscription | None:
        """Renew a user's subscription."""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            logger.warning("No active subscription found for user %s", user_id)
            return None

        plan = self.storage.get_payment_plan(subscription.plan_id)
        if not plan:
            logger.error("Payment plan %s not found for subscription renewal", subscription.plan_id)
            return None

        # Calculate new billing period
        now = datetime.now(timezone.utc)
        current_period_start = now
        current_period_end = None

        if plan.billing_period:
            period_mapping = {
                BillingPeriod.DAILY: timedelta(days=1),
                BillingPeriod.WEEKLY: timedelta(weeks=1),
                BillingPeriod.MONTHLY: timedelta(days=30),
                BillingPeriod.YEARLY: timedelta(days=365),
            }
            billing_period = (
                plan.billing_period if isinstance(plan.billing_period, BillingPeriod) else BillingPeriod(plan.billing_period)
            )
            current_period_end = now + period_mapping.get(billing_period, timedelta(days=30))

        subscription.current_period_start = current_period_start
        subscription.current_period_end = current_period_end
        subscription.usage_count = 0
        subscription.set_status("active")

        self.storage.save_subscription(subscription)
        logger.info("Renewed subscription for user %s", user_id)
        return subscription

    def check_subscription_access(self, user_id: str, feature: str) -> bool:
        """Check if a user has access to a feature based on their subscription."""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            logger.debug("User %s has no active subscription", user_id)
            return False

        plan = self.storage.get_payment_plan(subscription.plan_id)
        if not plan:
            logger.error("Payment plan %s not found for access check", subscription.plan_id)
            return False

        # Check if feature is included in the plan
        if feature not in plan.features:
            logger.debug("Feature %s not included in plan %s", feature, plan.id)
            return False

        # Check subscription expiration
        if subscription.current_period_end:
            now = datetime.now(timezone.utc)
            period_end = subscription.current_period_end
            if isinstance(period_end, str):
                try:
                    period_end = datetime.fromisoformat(period_end)
                except Exception:
                    return False
            if now > period_end:
                logger.debug("User %s subscription expired on %s", user_id, subscription.current_period_end)
                return False

        # Check usage limits for all plan types (not just pay-per-use)
        if plan.requests_per_period and subscription.usage_count >= plan.requests_per_period:
            logger.debug(
                "User %s has exceeded usage limit for feature %s (%d/%d)",
                user_id,
                feature,
                subscription.usage_count,
                plan.requests_per_period,
            )
            return False

        return True


class PaymentManager:
    """Main class for managing payments, subscriptions, and usage tracking."""

    def __init__(
        self,
        storage: StorageBackend | None = None,
        payment_provider: PaymentProvider | None = None,
        default_plan: str | None = None,
    ):
        """Initialize the payment manager."""
        # Use environment-aware storage initialization if no storage provided
        if storage is None:
            storage = _create_environment_aware_storage()

        self.storage = storage
        self.payment_provider = payment_provider or create_payment_provider("mock")
        self.default_plan = default_plan
        self.usage_tracker = UsageTracker(self.storage)
        self.subscription_manager = SubscriptionManager(self.storage)
        logger.info(
            "PaymentManager initialized with provider: %s, storage: %s", self.payment_provider.name, type(self.storage).__name__
        )

    def create_payment_plan(self, plan: PaymentPlan) -> None:
        """Create a new payment plan."""
        if not isinstance(plan, PaymentPlan):
            raise ValidationError("Plan must be a PaymentPlan instance", field="plan", value=plan)

        existing_plan = self.storage.get_payment_plan(plan.id)
        if existing_plan:
            logger.warning("Payment plan %s already exists, updating", plan.id)

        self.storage.save_payment_plan(plan)
        logger.info("Created/updated payment plan: %s", plan.id)

    def get_payment_plan(self, plan_id: str) -> PaymentPlan | None:
        """Get a payment plan by ID."""
        return self.storage.get_payment_plan(plan_id)

    def list_payment_plans(self) -> list[PaymentPlan]:
        """List all payment plans."""
        return self.storage.list_payment_plans()

    def subscribe_user(self, user_id: str, plan_id: str, metadata: dict[str, Any] | None = None) -> Subscription:
        """Subscribe a user to a payment plan."""
        return self.subscription_manager.create_subscription(user_id, plan_id, metadata)

    def cancel_user_subscription(self, user_id: str) -> bool:
        """Cancel a user's subscription."""
        return self.subscription_manager.cancel_subscription(user_id)

    def process_payment(
        self,
        user_id: str,
        amount: float,
        currency: str = "USD",
        metadata: dict[str, Any] | None = None,
    ) -> PaymentTransaction:
        """Process a payment for a user."""
        if not user_id or not isinstance(user_id, str):
            raise ValidationError("User ID is required and must be a string", field="user_id", value=user_id)
        if not isinstance(amount, (int, float)) or amount < 0:
            raise ValidationError("Amount must be a non-negative number", field="amount", value=amount)

        try:
            transaction = self.payment_provider.process_payment(user_id, amount, currency, metadata)

            logger.info("Processed payment for user %s: %.2f %s", user_id, amount, currency)
            return transaction
        except Exception as e:
            logger.error("Payment processing failed for user %s: %s", user_id, e)
            raise PaymentFailed(f"Payment processing failed: {e}", transaction_id=user_id)

    def verify_payment(self, transaction_id: str) -> bool:
        """Verify a payment transaction."""
        try:
            return self.payment_provider.verify_payment(transaction_id)
        except Exception as e:
            logger.error("Payment verification failed for transaction %s: %s", transaction_id, e)
            return False

    def get_user_usage(
        self,
        user_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[UsageRecord]:
        """Get usage records for a user."""
        return self.usage_tracker.get_user_usage(user_id, start_date, end_date)

    def get_user_subscription(self, user_id: str) -> Subscription | None:
        """Get the active subscription for a user."""
        return self.subscription_manager.get_user_subscription(user_id)

    def check_access(self, user_id: str, feature: str) -> bool:
        """Check if a user has access to a feature."""
        # Validate inputs
        if not user_id or not user_id.strip():
            raise ValidationError("user_id cannot be empty")
        if not feature or not feature.strip():
            raise ValidationError("feature cannot be empty")

        # Check subscription access first
        if self.subscription_manager.check_subscription_access(user_id, feature):
            return True

        # Check freemium plans for access and usage limits
        plans = self.list_payment_plans()
        for plan in plans:
            if plan.is_freemium() and feature in plan.features:
                usage_count = self.usage_tracker.get_usage_count(user_id, feature)
                if usage_count < plan.free_requests:
                    logger.debug(
                        "Freemium access granted for user %s to feature %s (%d/%d)",
                        user_id,
                        feature,
                        usage_count,
                        plan.free_requests,
                    )
                    return True
                else:
                    logger.debug(
                        "Freemium usage limit exceeded for user %s to feature %s (%d/%d)",
                        user_id,
                        feature,
                        usage_count,
                        plan.free_requests,
                    )
                    return False

        # Check if there's a default plan for pay-per-use
        if self.default_plan:
            plan = self.get_payment_plan(self.default_plan)
            if plan and plan.is_pay_per_use() and feature in plan.features:
                logger.debug("User %s can access feature %s via default pay-per-use plan", user_id, feature)
                return True

        logger.debug("User %s denied access to feature %s", user_id, feature)
        return False

    def get_default_plan(self) -> PaymentPlan | None:
        """Get the default payment plan."""
        if self.default_plan:
            return self.get_payment_plan(self.default_plan)
        return None

    def record_usage(self, user_id: str, feature: str, cost: float | None = None) -> UsageRecord:
        """Record usage for a user and feature, enforcing usage limits. Returns the UsageRecord."""
        # Validate inputs
        if not user_id or not user_id.strip():
            raise ValidationError("user_id cannot be empty")
        if not feature or not feature.strip():
            raise ValidationError("feature cannot be empty")
        if cost is not None and cost < 0:
            raise ValidationError("cost cannot be negative")

        # Use atomic operation to check limits and record usage
        return self._atomic_record_usage(user_id, feature, cost)

    def _atomic_record_usage(self, user_id: str, feature: str, cost: float | None = None) -> UsageRecord:
        """Atomically check limits and record usage to prevent race conditions."""
        # Use storage transaction if supported
        supports_txn = getattr(self.storage, "supports_transactions", None)
        if callable(supports_txn) and supports_txn():
            return self._transactional_record_usage(user_id, feature, cost)
        else:
            # Fallback to non-transactional approach with locks
            return self._locked_record_usage(user_id, feature, cost)

    def _transactional_record_usage(self, user_id: str, feature: str, cost: float | None = None) -> UsageRecord:
        """Record usage using storage transactions for true atomicity."""
        try:
            # Begin transaction if method exists
            begin_txn = getattr(self.storage, "begin_transaction", None)
            if callable(begin_txn):
                begin_txn()

            # Get all plans that might affect this feature
            plans = self.list_payment_plans()

            # Check freemium plans first
            for plan in plans:
                if plan.is_freemium() and feature in plan.features:
                    # Get current usage count atomically within transaction
                    usage_count = self.usage_tracker.get_usage_count(user_id, feature)
                    if usage_count >= plan.free_requests:
                        rollback = getattr(self.storage, "rollback", None)
                        if callable(rollback):
                            rollback()
                        raise UsageLimitExceeded(
                            f"Usage limit exceeded for feature: {feature}",
                            feature=feature,
                            current_usage=usage_count,
                            limit=plan.free_requests,
                        )

            # Check subscription plans
            subscription = self.get_user_subscription(user_id)
            if subscription:
                sub_plan = self.get_payment_plan(subscription.plan_id)
                if sub_plan and sub_plan.requests_per_period is not None and feature in sub_plan.features:
                    if subscription.usage_count >= sub_plan.requests_per_period:
                        rollback = getattr(self.storage, "rollback", None)
                        if callable(rollback):
                            rollback()
                        raise UsageLimitExceeded(
                            f"Usage limit exceeded for feature: {feature}",
                            feature=feature,
                            current_usage=subscription.usage_count,
                            limit=sub_plan.requests_per_period,
                        )

            # If we get here, usage is allowed - record it atomically
            record = self.usage_tracker.record_usage(user_id, feature, cost)
            logger.info(f"Recorded usage for user {user_id}, feature {feature}, cost: {cost or 0.0}")

            # Update subscription usage count atomically
            if subscription:
                subscription.increment_usage()
                self.storage.save_subscription(subscription)

            # Commit transaction if method exists
            commit = getattr(self.storage, "commit", None)
            if callable(commit):
                commit()
            return record

        except Exception as e:
            # Rollback on any error if method exists
            try:
                rollback = getattr(self.storage, "rollback", None)
                if callable(rollback):
                    rollback()
            except Exception as rollback_error:
                logger.error("Failed to rollback transaction: %s", rollback_error)
            raise e

    def _locked_record_usage(self, user_id: str, feature: str, cost: float | None = None) -> UsageRecord:
        """Record usage using locks for storage backends without transaction support."""
        # Use a lock to prevent race conditions
        if not hasattr(self, "_usage_lock"):
            import threading

            self._usage_lock = threading.RLock()

        with self._usage_lock:
            # Get all plans that might affect this feature
            plans = self.list_payment_plans()

            # Check freemium plans first
            for plan in plans:
                if plan.is_freemium() and feature in plan.features:
                    # Get current usage count atomically
                    usage_count = self.usage_tracker.get_usage_count(user_id, feature)
                    if usage_count >= plan.free_requests:
                        raise UsageLimitExceeded(
                            f"Usage limit exceeded for feature: {feature}",
                            feature=feature,
                            current_usage=usage_count,
                            limit=plan.free_requests,
                        )

            # Check subscription plans
            subscription = self.get_user_subscription(user_id)
            if subscription:
                sub_plan = self.get_payment_plan(subscription.plan_id)
                if sub_plan and sub_plan.requests_per_period is not None and feature in sub_plan.features:
                    if subscription.usage_count >= sub_plan.requests_per_period:
                        raise UsageLimitExceeded(
                            f"Usage limit exceeded for feature: {feature}",
                            feature=feature,
                            current_usage=subscription.usage_count,
                            limit=sub_plan.requests_per_period,
                        )

            # If we get here, usage is allowed - record it atomically
            record = self.usage_tracker.record_usage(user_id, feature, cost)
            logger.info(f"Recorded usage for user {user_id}, feature {feature}, cost: {cost or 0.0}")

            # Update subscription usage count atomically
            if subscription:
                subscription.increment_usage()
                self.storage.save_subscription(subscription)

            return record

    def paid_feature(
        self,
        feature_name: str | None = None,
        cost: float | None = None,
        plan_id: str | None = None,
    ):
        """Decorator for paid features."""

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(user_id: str, *args, **kwargs):
                feature = feature_name or func.__name__
                # Check if user has access
                if not self.check_access(user_id, feature):
                    # Check for usage limit exceeded in freemium plans
                    plans = self.list_payment_plans()
                    for plan in plans:
                        if plan.is_freemium() and feature in plan.features:
                            usage_count = self.usage_tracker.get_usage_count(user_id, feature)
                            if usage_count >= plan.free_requests:
                                raise UsageLimitExceeded(
                                    f"Usage limit exceeded for feature: {feature}",
                                    feature=feature,
                                    current_usage=usage_count,
                                    limit=plan.free_requests,
                                )
                    # Check for usage limit exceeded in subscription plans
                    subscription = self.get_user_subscription(user_id)
                    if subscription:
                        sub_plan = self.get_payment_plan(subscription.plan_id)
                        if sub_plan and sub_plan.requests_per_period is not None and feature in sub_plan.features:
                            if subscription.usage_count >= sub_plan.requests_per_period:
                                raise UsageLimitExceeded(
                                    f"Usage limit exceeded for feature: {feature}",
                                    feature=feature,
                                    current_usage=subscription.usage_count,
                                    limit=sub_plan.requests_per_period,
                                )
                    raise PaymentRequired(
                        f"Payment required for feature: {feature}",
                        feature=feature,
                        required_amount=cost,
                    )
                # Call the function first, then record usage
                result = func(user_id, *args, **kwargs)
                self.record_usage(user_id, feature, cost)
                return result

            return wrapper

        return decorator

    def subscription_required(self, plan_id: str):
        """Decorator for subscription-required features."""

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(user_id: str, *args, **kwargs):
                subscription = self.get_user_subscription(user_id)
                if not subscription or subscription.plan_id != plan_id:
                    raise SubscriptionExpired(
                        f"Subscription to plan {plan_id} required",
                        plan_id=plan_id,
                    )
                return func(user_id, *args, **kwargs)

            return wrapper

        return decorator

    def usage_limit(self, max_uses: int, feature_name: str | None = None):
        """Decorator for usage-limited features."""

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(user_id: str, *args, **kwargs):
                feature = feature_name or func.__name__
                current_usage = self.usage_tracker.get_usage_count(user_id, feature)

                if current_usage >= max_uses:
                    raise UsageLimitExceeded(
                        f"Usage limit exceeded for feature: {feature}",
                        feature=feature,
                        current_usage=current_usage,
                        limit=max_uses,
                    )

                self.record_usage(user_id, feature)
                return func(user_id, *args, **kwargs)

            return wrapper

        return decorator
