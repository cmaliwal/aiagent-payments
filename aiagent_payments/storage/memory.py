"""
In-memory storage backend for development and testing.

This backend stores all data in memory and is not persistent.
"""

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..exceptions import StorageError, ValidationError
from ..models import PaymentPlan, PaymentTransaction, Subscription, UsageRecord
from .base import StorageBackend

logger = logging.getLogger(__name__)


class MemoryStorage(StorageBackend):
    """
    In-memory storage backend for development and testing.

    This backend provides transaction support through a simple lock mechanism
    to ensure atomic operations and prevent race conditions.
    """

    def __init__(self):
        """Initialize the memory storage backend."""
        self.payment_plans: Dict[str, PaymentPlan] = {}
        self.subscriptions: Dict[str, Subscription] = {}
        self.user_subscriptions: Dict[str, str] = {}  # user_id -> subscription_id
        self.usage_records: Dict[str, UsageRecord] = {}
        self.transactions: Dict[str, PaymentTransaction] = {}

        # Thread safety
        self._lock = threading.RLock()
        self._transaction_lock = threading.RLock()

        # Thread-local transaction state
        self._transaction_local = threading.local()
        self._transaction_local.in_transaction = False
        self._transaction_local.transaction_data = {}

        super().__init__("MemoryStorage")
        logger.info("MemoryStorage initialized")

    def _get_capabilities(self):
        """
        Get the capabilities of this storage backend.
        Returns:
            StorageCapabilities object describing supported features
        """
        from .base import StorageCapabilities

        return StorageCapabilities(
            supports_transactions=True,  # Now supports transactions
            supports_encryption=False,
            supports_backup=False,
            supports_search=False,
            supports_indexing=False,
            max_data_size=100 * 1024 * 1024,  # 100 MB
            supports_concurrent_access=True,
            supports_pagination=True,
            supports_bulk_operations=True,
        )

    def _validate_configuration(self):
        """Validate the storage backend configuration."""
        # No configuration needed for memory storage
        pass

    def _perform_health_check(self):
        """Perform a health check for the MemoryStorage backend."""
        try:
            # Simple health check - verify we can access our data structures
            _ = len(self.payment_plans)
            _ = len(self.subscriptions)
            _ = len(self.usage_records)
            _ = len(self.transactions)
        except Exception as e:
            raise Exception(f"MemoryStorage health check failed: {e}")

    def begin_transaction(self) -> Any:
        """Begin a transaction for atomic operations."""
        with self._transaction_lock:
            # Check thread-local transaction state
            if getattr(self._transaction_local, "in_transaction", False):
                raise StorageError("Transaction already in progress")

            # Create a snapshot of current data
            self._transaction_local.transaction_data = {
                "payment_plans": self.payment_plans.copy(),
                "subscriptions": self.subscriptions.copy(),
                "user_subscriptions": self.user_subscriptions.copy(),
                "usage_records": self.usage_records.copy(),
                "transactions": self.transactions.copy(),
            }
            self._transaction_local.in_transaction = True

            logger.debug("MemoryStorage transaction begun")
            return True

    def commit(self) -> None:
        """Commit the current transaction."""
        with self._transaction_lock:
            # Check thread-local transaction state
            if not getattr(self._transaction_local, "in_transaction", False):
                raise StorageError("No transaction in progress")

            # Transaction data is already applied, just clear the transaction state
            self._transaction_local.transaction_data = {}
            self._transaction_local.in_transaction = False

            logger.debug("MemoryStorage transaction committed")

    def rollback(self) -> None:
        """Rollback the current transaction."""
        with self._transaction_lock:
            # Check thread-local transaction state
            if not getattr(self._transaction_local, "in_transaction", False):
                raise StorageError("No transaction in progress")

            # Restore data from transaction snapshot
            transaction_data = getattr(self._transaction_local, "transaction_data", {})
            self.payment_plans = transaction_data.get("payment_plans", {}).copy()
            self.subscriptions = transaction_data.get("subscriptions", {}).copy()
            self.user_subscriptions = transaction_data.get("user_subscriptions", {}).copy()
            self.usage_records = transaction_data.get("usage_records", {}).copy()
            self.transactions = transaction_data.get("transactions", {}).copy()

            self._transaction_local.transaction_data = {}
            self._transaction_local.in_transaction = False

            logger.debug("MemoryStorage transaction rolled back")

    def save_payment_plan(self, plan: PaymentPlan) -> None:
        """
        Save a payment plan to memory storage.

        Args:
            plan: PaymentPlan object to save

        Raises:
            ValidationError: If the plan is invalid
        """
        if not plan or not isinstance(plan, PaymentPlan):
            raise ValidationError("Invalid payment plan object", field="plan", value=plan)

        # Validate data size before saving (maintains consistency with StorageBackend contract)
        self._validate_and_save_data(plan)

        # Validate the plan before saving
        plan.validate()

        self.payment_plans[plan.id] = plan
        logger.info("Saved payment plan: %s", plan.id)

    def get_payment_plan(self, plan_id: str) -> Optional[PaymentPlan]:
        """
        Retrieve a payment plan by ID.

        Args:
            plan_id: ID of the payment plan to retrieve

        Returns:
            PaymentPlan object if found, None otherwise

        Raises:
            ValidationError: If the plan_id is invalid
        """
        if plan_id == "":
            return None
        if not plan_id or not isinstance(plan_id, str):
            raise ValidationError("Invalid plan_id", field="plan_id", value=plan_id)

        plan = self.payment_plans.get(plan_id)
        if plan:
            logger.debug("Retrieved payment plan: %s", plan_id)
        else:
            logger.debug("Payment plan not found: %s", plan_id)
        return plan

    def list_payment_plans(self) -> List[PaymentPlan]:
        """
        List all payment plans.

        Returns:
            List of PaymentPlan objects
        """
        plans = list(self.payment_plans.values())
        logger.debug("Retrieved %d payment plans", len(plans))
        return plans

    def save_subscription(self, subscription: Subscription) -> None:
        """
        Save a subscription to memory storage.

        Args:
            subscription: Subscription object to save

        Raises:
            ValidationError: If the subscription is invalid
        """
        if not subscription or not isinstance(subscription, Subscription):
            raise ValidationError("Invalid subscription object", field="subscription", value=subscription)

        # Validate data size before saving (maintains consistency with StorageBackend contract)
        self._validate_and_save_data(subscription)

        # Validate the subscription before saving
        subscription.validate()

        self.subscriptions[subscription.id] = subscription
        if subscription.status == "active":
            self.user_subscriptions[subscription.user_id] = subscription.id
        logger.info("Saved subscription: %s for user: %s", subscription.id, subscription.user_id)

    def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        """
        Retrieve a subscription by ID.

        Args:
            subscription_id: ID of the subscription to retrieve

        Returns:
            Subscription object if found, None otherwise

        Raises:
            ValidationError: If the subscription_id is invalid
        """
        if subscription_id == "":
            return None
        if not subscription_id or not isinstance(subscription_id, str):
            raise ValidationError("Invalid subscription_id", field="subscription_id", value=subscription_id)

        subscription = self.subscriptions.get(subscription_id)
        if subscription:
            logger.debug("Retrieved subscription: %s", subscription_id)
        else:
            logger.debug("Subscription not found: %s", subscription_id)
        return subscription

    def get_user_subscription(self, user_id: str) -> Optional[Subscription]:
        """
        Retrieve the active subscription for a user.

        Args:
            user_id: ID of the user

        Returns:
            Active Subscription object if found, None otherwise

        Raises:
            ValidationError: If the user_id is invalid
        """
        if user_id == "":
            return None
        if not user_id or not isinstance(user_id, str):
            raise ValidationError("Invalid user_id", field="user_id", value=user_id)

        subscription_id = self.user_subscriptions.get(user_id)
        if subscription_id:
            subscription = self.get_subscription(subscription_id)
            if subscription:
                logger.debug("Retrieved active subscription for user %s: %s", user_id, subscription_id)
                return subscription
        logger.debug("No active subscription found for user: %s", user_id)
        return None

    def save_usage_record(self, record: UsageRecord) -> None:
        """
        Save a usage record to memory storage.

        Args:
            record: UsageRecord object to save

        Raises:
            ValidationError: If the record is invalid
        """
        if not record or not isinstance(record, UsageRecord):
            raise ValidationError("Invalid usage record object", field="record", value=record)

        # Validate data size before saving (maintains consistency with StorageBackend contract)
        self._validate_and_save_data(record)

        # Validate the record before saving
        record.validate()

        self.usage_records[record.id] = record
        logger.debug(
            "Saved usage record: %s for user: %s, feature: %s",
            record.id,
            record.user_id,
            record.feature,
        )

    def get_user_usage(
        self, user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[UsageRecord]:
        """
        Retrieve usage records for a user within a date range.

        Args:
            user_id: ID of the user
            start_date: Start date for the range (inclusive)
            end_date: End date for the range (inclusive)

        Returns:
            List of UsageRecord objects

        Raises:
            ValidationError: If the user_id is invalid
        """
        if not user_id or not isinstance(user_id, str):
            raise ValidationError("Invalid user_id", field="user_id", value=user_id)

        records = [r for r in self.usage_records.values() if r.user_id == user_id]
        if start_date:
            records = [r for r in records if r.timestamp >= start_date]
        if end_date:
            records = [r for r in records if r.timestamp <= end_date]

        filtered_records = sorted(records, key=lambda x: x.timestamp)
        logger.debug("Retrieved %d usage records for user %s", len(filtered_records), user_id)
        return filtered_records

    def save_transaction(self, transaction: PaymentTransaction) -> None:
        """
        Save a payment transaction to memory storage.

        Args:
            transaction: PaymentTransaction object to save

        Raises:
            ValidationError: If the transaction is invalid
        """
        if not transaction or not isinstance(transaction, PaymentTransaction):
            raise ValidationError("Invalid transaction object", field="transaction", value=transaction)

        # Validate data size before saving (maintains consistency with StorageBackend contract)
        self._validate_and_save_data(transaction)

        # Validate the transaction before saving
        transaction.validate()

        self.transactions[transaction.id] = transaction
        logger.debug(
            "Saved transaction: %s for user: %s, amount: %.2f",
            transaction.id,
            transaction.user_id,
            transaction.amount,
        )

    def update_transaction(self, transaction: PaymentTransaction) -> None:
        """
        Update an existing payment transaction in memory storage.

        Args:
            transaction: PaymentTransaction object to update

        Raises:
            ValidationError: If the transaction is invalid
            StorageError: If the transaction does not exist
        """
        if not transaction or not isinstance(transaction, PaymentTransaction):
            raise ValidationError("Invalid transaction object", field="transaction", value=transaction)
        if transaction.id not in self.transactions:
            raise StorageError(f"Transaction with id {transaction.id} does not exist")
        self._validate_and_save_data(transaction)
        transaction.validate()
        self.transactions[transaction.id] = transaction
        logger.debug(
            "Updated transaction: %s for user: %s, amount: %.2f",
            transaction.id,
            transaction.user_id,
            transaction.amount,
        )

    def get_transaction(self, transaction_id: str) -> Optional[PaymentTransaction]:
        """
        Retrieve a payment transaction by ID.

        Args:
            transaction_id: ID of the transaction to retrieve

        Returns:
            PaymentTransaction object if found, None otherwise

        Raises:
            ValidationError: If the transaction_id is invalid
        """
        if transaction_id == "":
            return None
        if not transaction_id or not isinstance(transaction_id, str):
            raise ValidationError("Invalid transaction_id", field="transaction_id", value=transaction_id)

        transaction = self.transactions.get(transaction_id)
        if transaction:
            logger.debug("Retrieved transaction: %s", transaction_id)
        else:
            logger.debug("Transaction not found: %s", transaction_id)
        return transaction

    def get_transactions_by_user_id(self, user_id: str) -> List[PaymentTransaction]:
        """
        Retrieve all transactions for a specific user.

        Args:
            user_id: ID of the user

        Returns:
            List of PaymentTransaction objects for the user

        Raises:
            ValidationError: If the user_id is invalid
        """
        if not user_id or not isinstance(user_id, str):
            raise ValidationError("Invalid user_id", field="user_id", value=user_id)

        user_transactions = [tx for tx in self.transactions.values() if tx.user_id == user_id]
        user_transactions.sort(key=lambda x: x.created_at, reverse=True)
        logger.debug("Retrieved %d transactions for user %s", len(user_transactions), user_id)
        return user_transactions

    def list_transactions(
        self, user_id: Optional[str] = None, status: Optional[str] = None, limit: Optional[int] = None
    ) -> List[PaymentTransaction]:
        """
        List transactions with optional filtering.

        Args:
            user_id: Optional user ID to filter by
            status: Optional status to filter by
            limit: Optional limit on number of transactions to return

        Returns:
            List of PaymentTransaction objects matching the filters
        """
        transactions = list(self.transactions.values())

        # Apply filters
        if user_id:
            transactions = [tx for tx in transactions if tx.user_id == user_id]
        if status:
            transactions = [tx for tx in transactions if tx.status == status]

        # Sort by creation date (newest first)
        transactions.sort(key=lambda x: x.created_at, reverse=True)

        # Apply limit
        if limit:
            transactions = transactions[:limit]

        logger.debug(
            "Retrieved %d transactions with filters: user_id=%s, status=%s, limit=%s", len(transactions), user_id, status, limit
        )
        return transactions

    def get_storage_stats(self) -> dict:
        """
        Get statistics about the stored data.

        Returns:
            Dictionary containing storage statistics
        """
        return {
            "payment_plans": len(self.payment_plans),
            "subscriptions": len(self.subscriptions),
            "usage_records": len(self.usage_records),
            "transactions": len(self.transactions),
            "active_user_subscriptions": len(self.user_subscriptions),
        }
