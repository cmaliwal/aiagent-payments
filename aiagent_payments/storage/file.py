"""
File-based storage backend using JSON files.
"""

import json
import logging
import os
import threading
from datetime import datetime
from typing import Any

from ..exceptions import StorageError, ValidationError
from ..models import PaymentPlan, PaymentTransaction, Subscription, UsageRecord
from ..utils import retry
from .base import StorageBackend

try:
    import fcntl

    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

try:
    import msvcrt

    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

logger = logging.getLogger(__name__)


class FileStorage(StorageBackend):
    """
    File-based storage backend using JSON files.

    This backend provides transaction support through file locking and temporary files
    to ensure atomic operations and prevent race conditions.
    """

    def __init__(self, data_dir: str = "aiagent_payments_data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.plans_file = os.path.join(data_dir, "payment_plans.json")
        self.subscriptions_file = os.path.join(data_dir, "subscriptions.json")
        self.usage_file = os.path.join(data_dir, "usage_records.json")
        self.transactions_file = os.path.join(data_dir, "transactions.json")
        self.user_subscriptions_file = os.path.join(data_dir, "user_subscriptions.json")

        # Thread safety and transaction support
        self._lock = threading.RLock()
        self._transaction_lock = threading.RLock()

        # Thread-local transaction state
        self._transaction_local = threading.local()
        self._transaction_local.in_transaction = False
        self._transaction_local.transaction_data = {}
        self._transaction_local.transaction_files = {}

        super().__init__("FileStorage")
        logger.info("FileStorage initialized with data directory: %s", data_dir)

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
            supports_backup=True,
            supports_search=False,
            supports_indexing=False,
            max_data_size=100 * 1024 * 1024,  # 100 MB
            supports_concurrent_access=True,  # With file locking
            supports_pagination=False,
            supports_bulk_operations=False,
        )

    def _validate_configuration(self):
        """Validate the storage backend configuration."""
        if not self.data_dir or not isinstance(self.data_dir, str):
            raise ValidationError("data_dir must be a non-empty string", field="data_dir", value=self.data_dir)

        # Check if directory is writable
        if not os.access(self.data_dir, os.W_OK):
            raise ValidationError(f"Data directory {self.data_dir} is not writable", field="data_dir", value=self.data_dir)

    def _perform_health_check(self):
        """Perform a health check for the FileStorage backend."""
        try:
            # Check if we can read and write to the data directory
            test_file = os.path.join(self.data_dir, ".health_check")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            raise Exception(f"FileStorage health check failed: {e}")

    def begin_transaction(self) -> Any:
        """Begin a transaction for atomic operations."""
        with self._transaction_lock:
            # Check thread-local transaction state
            if getattr(self._transaction_local, "in_transaction", False):
                raise StorageError("Transaction already in progress")

            # Create a snapshot of current data
            self._transaction_local.transaction_data = {
                "payment_plans": self._load_json(self.plans_file).copy(),
                "subscriptions": self._load_json(self.subscriptions_file).copy(),
                "user_subscriptions": self._load_json(self.user_subscriptions_file).copy(),
                "usage_records": self._load_json(self.usage_file).copy(),
                "transactions": self._load_json(self.transactions_file).copy(),
            }

            # Create temporary files for transaction
            self._transaction_local.transaction_files = {
                "payment_plans": self.plans_file + ".tmp",
                "subscriptions": self.subscriptions_file + ".tmp",
                "user_subscriptions": self.user_subscriptions_file + ".tmp",
                "usage_records": self.usage_file + ".tmp",
                "transactions": self.transactions_file + ".tmp",
            }

            self._transaction_local.in_transaction = True
            logger.debug("FileStorage transaction begun")
            return True

    def commit(self) -> None:
        """Commit the current transaction."""
        with self._transaction_lock:
            # Check thread-local transaction state
            if not getattr(self._transaction_local, "in_transaction", False):
                raise StorageError("No transaction in progress")

            try:
                # Write transaction data to temporary files
                transaction_files = getattr(self._transaction_local, "transaction_files", {})
                transaction_data = getattr(self._transaction_local, "transaction_data", {})

                for file_type, temp_file in transaction_files.items():
                    data = transaction_data.get(file_type, {})
                    self._save_json(temp_file, data)

                # Atomically move temporary files to actual files
                for file_type, temp_file in transaction_files.items():
                    actual_file = getattr(self, f"{file_type.replace('_', '')}_file")
                    if os.path.exists(temp_file):
                        os.replace(temp_file, actual_file)

                # Clear transaction state
                self._transaction_local.transaction_data = {}
                self._transaction_local.transaction_files = {}
                self._transaction_local.in_transaction = False

                logger.debug("FileStorage transaction committed")

            except Exception as e:
                # Clean up temporary files on error
                transaction_files = getattr(self._transaction_local, "transaction_files", {})
                for temp_file in transaction_files.values():
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                    except Exception:
                        pass
                raise StorageError(f"Failed to commit transaction: {e}")

    def rollback(self) -> None:
        """Rollback the current transaction."""
        with self._transaction_lock:
            # Check thread-local transaction state
            if not getattr(self._transaction_local, "in_transaction", False):
                raise StorageError("No transaction in progress")

            # Clean up temporary files
            transaction_files = getattr(self._transaction_local, "transaction_files", {})
            for temp_file in transaction_files.values():
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception:
                    pass

            # Clear transaction state
            self._transaction_local.transaction_data = {}
            self._transaction_local.transaction_files = {}
            self._transaction_local.in_transaction = False

            logger.debug("FileStorage transaction rolled back")

    def _load_json(self, filepath: str) -> dict[str, Any]:
        if os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    # File locking for read operations
                    if HAS_FCNTL:
                        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    elif HAS_MSVCRT:
                        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)

                    try:
                        data = json.load(f)
                        logger.debug("Loaded data from: %s", filepath)
                        return data
                    finally:
                        # Release lock
                        if HAS_FCNTL:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                        elif HAS_MSVCRT:
                            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Error loading data from %s: %s", filepath, str(e))
                return {}
        return {}

    def _save_json(self, filepath: str, data: dict[str, Any]) -> None:
        try:
            with open(filepath, "w") as f:
                # File locking for write operations
                if HAS_FCNTL:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                elif HAS_MSVCRT:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)

                try:
                    json.dump(data, f, indent=2, default=str)
                    logger.debug("Saved data to: %s", filepath)
                finally:
                    # Release lock
                    if HAS_FCNTL:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    elif HAS_MSVCRT:
                        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError as e:
            logger.error("Error saving data to %s: %s", filepath, str(e))
            raise StorageError(f"Failed to save data to {filepath}: {str(e)}")

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying file save...")
    def save_payment_plan(self, plan: PaymentPlan) -> None:
        if not plan or not isinstance(plan, PaymentPlan):
            raise ValidationError("Invalid payment plan object", field="plan", value=plan)

        # Validate data size before saving
        self._validate_and_save_data(plan)

        try:
            data = self._load_json(self.plans_file)
            data[plan.id] = plan.to_dict()
            self._save_json(self.plans_file, data)
            logger.info("Saved payment plan: %s", plan.id)
        except Exception as e:
            logger.error("Error saving payment plan: %s", str(e))
            raise StorageError(f"Failed to save payment plan: {str(e)}")

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying file read...")
    def get_payment_plan(self, plan_id: str) -> PaymentPlan | None:
        if not plan_id or not isinstance(plan_id, str):
            raise ValidationError("Invalid plan_id", field="plan_id", value=plan_id)
        try:
            data = self._load_json(self.plans_file)
            plan_data = data.get(plan_id)
            if plan_data:
                try:
                    plan = PaymentPlan(**plan_data)
                    logger.debug("Retrieved payment plan: %s", plan_id)
                    return plan
                except Exception as e:
                    logger.error("Error deserializing payment plan %s: %s", plan_id, str(e))
                    return None
            logger.debug("Payment plan not found: %s", plan_id)
            return None
        except Exception as e:
            logger.error("Error reading payment plan: %s", str(e))
            raise StorageError(f"Failed to read payment plan: {str(e)}")

    def list_payment_plans(self) -> list[PaymentPlan]:
        data = self._load_json(self.plans_file)
        plans = []
        for plan_data in data.values():
            try:
                plan = PaymentPlan(**plan_data)
                plans.append(plan)
            except Exception as e:
                logger.error("Error deserializing payment plan: %s", str(e))
        logger.debug("Retrieved %d payment plans", len(plans))
        return plans

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying file save...")
    def save_subscription(self, subscription: Subscription) -> None:
        if not subscription or not isinstance(subscription, Subscription):
            raise ValidationError("Invalid subscription object", field="subscription", value=subscription)

        # Validate data size before saving
        self._validate_and_save_data(subscription)

        try:
            data = self._load_json(self.subscriptions_file)
            data[subscription.id] = subscription.to_dict()
            self._save_json(self.subscriptions_file, data)
            if subscription.status == "active":
                user_data = self._load_json(self.user_subscriptions_file)
                user_data[subscription.user_id] = subscription.id
                self._save_json(self.user_subscriptions_file, user_data)
            logger.info(
                "Saved subscription: %s for user: %s",
                subscription.id,
                subscription.user_id,
            )
        except Exception as e:
            logger.error("Error saving subscription: %s", str(e))
            raise StorageError(f"Failed to save subscription: {str(e)}")

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying file read...")
    def get_subscription(self, subscription_id: str) -> Subscription | None:
        if not subscription_id or not isinstance(subscription_id, str):
            raise ValidationError(
                "Invalid subscription_id",
                field="subscription_id",
                value=subscription_id,
            )
        try:
            data = self._load_json(self.subscriptions_file)
            sub_data = data.get(subscription_id)
            if sub_data:
                try:
                    subscription = Subscription(**sub_data)
                    logger.debug("Retrieved subscription: %s", subscription_id)
                    return subscription
                except Exception as e:
                    logger.error(
                        "Error deserializing subscription %s: %s",
                        subscription_id,
                        str(e),
                    )
                    return None
            logger.debug("Subscription not found: %s", subscription_id)
            return None
        except Exception as e:
            logger.error("Error reading subscription: %s", str(e))
            raise StorageError(f"Failed to read subscription: {str(e)}")

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying file read...")
    def get_user_subscription(self, user_id: str) -> Subscription | None:
        if not user_id or not isinstance(user_id, str):
            raise ValidationError("Invalid user_id", field="user_id", value=user_id)
        try:
            user_data = self._load_json(self.user_subscriptions_file)
            subscription_id = user_data.get(user_id)
            if subscription_id:
                subscription = self.get_subscription(subscription_id)
                if subscription:
                    logger.debug(
                        "Retrieved active subscription for user %s: %s",
                        user_id,
                        subscription_id,
                    )
                    return subscription
            logger.debug("No active subscription found for user: %s", user_id)
            return None
        except Exception as e:
            logger.error("Error reading user subscription: %s", str(e))
            raise StorageError(f"Failed to read user subscription: {str(e)}")

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying file save...")
    def save_usage_record(self, record: UsageRecord) -> None:
        if not record or not isinstance(record, UsageRecord):
            raise ValidationError("Invalid usage record object", field="record", value=record)

        # Validate data size before saving
        self._validate_and_save_data(record)

        try:
            data = self._load_json(self.usage_file)
            data[record.id] = record.to_dict()
            self._save_json(self.usage_file, data)
            logger.debug(
                "Saved usage record: %s for user: %s, feature: %s",
                record.id,
                record.user_id,
                record.feature,
            )
        except Exception as e:
            logger.error("Error saving usage record: %s", str(e))
            raise StorageError(f"Failed to save usage record: {str(e)}")

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying file read...")
    def get_user_usage(
        self, user_id: str, start_date: datetime | None = None, end_date: datetime | None = None
    ) -> list[UsageRecord]:
        if not user_id or not isinstance(user_id, str):
            raise ValidationError("Invalid user_id", field="user_id", value=user_id)
        try:
            data = self._load_json(self.usage_file)
            records = []
            for record_data in data.values():
                if record_data["user_id"] == user_id:
                    try:
                        record = UsageRecord(**record_data)
                        if start_date and record.timestamp < start_date:
                            continue
                        if end_date and record.timestamp > end_date:
                            continue
                        records.append(record)
                    except Exception as e:
                        logger.error("Error deserializing usage record: %s", str(e))
            filtered_records = sorted(records, key=lambda x: x.timestamp)
            logger.debug("Retrieved %d usage records for user %s", len(filtered_records), user_id)
            return filtered_records
        except Exception as e:
            logger.error("Error reading usage records: %s", str(e))
            raise StorageError(f"Failed to read usage records: {str(e)}")

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying file save...")
    def save_transaction(self, transaction: PaymentTransaction) -> None:
        if not transaction or not isinstance(transaction, PaymentTransaction):
            raise ValidationError("Invalid transaction object", field="transaction", value=transaction)

        # Validate data size before saving
        self._validate_and_save_data(transaction)

        try:
            data = self._load_json(self.transactions_file)
            data[transaction.id] = transaction.to_dict()
            self._save_json(self.transactions_file, data)
            logger.debug(
                "Saved transaction: %s for user: %s, amount: %.2f",
                transaction.id,
                transaction.user_id,
                transaction.amount,
            )
        except Exception as e:
            logger.error("Error saving transaction: %s", str(e))
            raise StorageError(f"Failed to save transaction: {str(e)}")

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying file read...")
    def get_transaction(self, transaction_id: str) -> PaymentTransaction | None:
        if not transaction_id or not isinstance(transaction_id, str):
            raise ValidationError("Invalid transaction_id", field="transaction_id", value=transaction_id)
        try:
            data = self._load_json(self.transactions_file)
            tx_data = data.get(transaction_id)
            if tx_data:
                try:
                    transaction = PaymentTransaction(**tx_data)
                    logger.debug("Retrieved transaction: %s", transaction_id)
                    return transaction
                except Exception as e:
                    logger.error("Error deserializing transaction %s: %s", transaction_id, str(e))
                    return None
            logger.debug("Transaction not found: %s", transaction_id)
            return None
        except Exception as e:
            logger.error("Error reading transaction: %s", str(e))
            raise StorageError(f"Failed to read transaction: {str(e)}")

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying file read...")
    def get_transactions_by_user_id(self, user_id: str) -> list[PaymentTransaction]:
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
        try:
            data = self._load_json(self.transactions_file)
            transactions = []
            for tx_data in data.values():
                if tx_data["user_id"] == user_id:
                    try:
                        transaction = PaymentTransaction(**tx_data)
                        transactions.append(transaction)
                    except Exception as e:
                        logger.error("Error deserializing transaction: %s", str(e))

            # Sort by creation date (newest first)
            transactions.sort(key=lambda x: x.created_at, reverse=True)
            logger.debug("Retrieved %d transactions for user %s", len(transactions), user_id)
            return transactions
        except Exception as e:
            logger.error("Error reading transactions for user %s: %s", user_id, str(e))
            raise StorageError(f"Failed to read transactions: {str(e)}")

    @retry(exceptions=Exception, max_attempts=3, logger=logger, retry_message="Retrying file read...")
    def list_transactions(
        self, user_id: str | None = None, status: str | None = None, limit: int | None = None
    ) -> list[PaymentTransaction]:
        """
        List transactions with optional filtering.

        Args:
            user_id: Optional user ID to filter by
            status: Optional status to filter by
            limit: Optional limit on number of transactions to return

        Returns:
            List of PaymentTransaction objects matching the filters
        """
        try:
            data = self._load_json(self.transactions_file)
            transactions = []
            for tx_data in data.values():
                # Apply filters
                if user_id and tx_data["user_id"] != user_id:
                    continue
                if status and tx_data["status"] != status:
                    continue

                try:
                    transaction = PaymentTransaction(**tx_data)
                    transactions.append(transaction)
                except Exception as e:
                    logger.error("Error deserializing transaction: %s", str(e))

            # Sort by creation date (newest first)
            transactions.sort(key=lambda x: x.created_at, reverse=True)

            # Apply limit
            if limit:
                transactions = transactions[:limit]

            logger.debug(
                "Retrieved %d transactions with filters: user_id=%s, status=%s, limit=%s",
                len(transactions),
                user_id,
                status,
                limit,
            )
            return transactions
        except Exception as e:
            logger.error("Error reading transactions: %s", str(e))
            raise StorageError(f"Failed to read transactions: {str(e)}")

    def update_transaction(self, transaction: PaymentTransaction) -> None:
        """
        Update an existing payment transaction in file storage.

        Args:
            transaction: PaymentTransaction object to update

        Raises:
            ValidationError: If the transaction is invalid
            StorageError: If the transaction does not exist
        """
        if not transaction or not isinstance(transaction, PaymentTransaction):
            raise ValidationError("Invalid transaction object", field="transaction", value=transaction)
        data = self._load_json(self.transactions_file)
        if transaction.id not in data:
            raise StorageError(f"Transaction with id {transaction.id} does not exist")
        self._validate_and_save_data(transaction)
        data[transaction.id] = transaction.to_dict()
        self._save_json(self.transactions_file, data)
        logger.debug(
            "Updated transaction: %s for user: %s, amount: %.2f",
            transaction.id,
            transaction.user_id,
            transaction.amount,
        )
