"""
Abstract base class for storage backends.

Defines the interface that all storage backends must implement.
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..exceptions import StorageError
from ..models import PaymentPlan, PaymentTransaction, Subscription, UsageRecord

logger = logging.getLogger(__name__)


@dataclass
class StorageCapabilities:
    """Represents the capabilities of a storage backend."""

    supports_transactions: bool = False
    supports_encryption: bool = False
    supports_backup: bool = False
    supports_search: bool = False
    supports_indexing: bool = False
    max_data_size: Optional[int] = None
    supports_concurrent_access: bool = True
    supports_pagination: bool = True
    supports_bulk_operations: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert capabilities to dictionary."""
        return {
            "supports_transactions": self.supports_transactions,
            "supports_encryption": self.supports_encryption,
            "supports_backup": self.supports_backup,
            "supports_search": self.supports_search,
            "supports_indexing": self.supports_indexing,
            "max_data_size": self.max_data_size,
            "supports_concurrent_access": self.supports_concurrent_access,
            "supports_pagination": self.supports_pagination,
            "supports_bulk_operations": self.supports_bulk_operations,
        }


@dataclass
class StorageStatus:
    """Represents the current status of a storage backend."""

    is_healthy: bool = True
    last_check: Optional[datetime] = None
    error_message: Optional[str] = None
    response_time_ms: Optional[float] = None
    data_size_bytes: Optional[int] = None
    record_count: Optional[int] = None

    def __post_init__(self):
        if self.last_check is None:
            self.last_check = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert status to dictionary."""
        return {
            "is_healthy": self.is_healthy,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "error_message": self.error_message,
            "response_time_ms": self.response_time_ms,
            "data_size_bytes": self.data_size_bytes,
            "record_count": self.record_count,
        }


class StorageBackend(ABC):
    """
    Abstract base class for storage backends.

    Defines the interface that all storage backends must implement.
    """

    def __init__(self, name: str):
        """Initialize the storage backend."""
        self.name = name
        self.capabilities = self._get_capabilities()
        self.status = StorageStatus()
        self._validate_configuration()
        logger.info("Initialized storage backend: %s", self.name)

    @abstractmethod
    def _get_capabilities(self) -> StorageCapabilities:
        """Get the capabilities of this storage backend."""
        pass

    @abstractmethod
    def _validate_configuration(self) -> None:
        """Validate the storage backend configuration."""
        pass

    @abstractmethod
    def save_payment_plan(self, plan: PaymentPlan) -> None:
        """
        Save a payment plan to storage.

        Concrete implementations must call self._validate_and_save_data(plan)
        before performing the actual save operation to ensure data size validation.
        """
        pass

    @abstractmethod
    def get_payment_plan(self, plan_id: str) -> Optional[PaymentPlan]:
        """Retrieve a payment plan by ID."""
        pass

    @abstractmethod
    def list_payment_plans(self) -> List[PaymentPlan]:
        """List all payment plans."""
        pass

    @abstractmethod
    def save_subscription(self, subscription: Subscription) -> None:
        """
        Save a subscription to storage.

        Concrete implementations must call self._validate_and_save_data(subscription)
        before performing the actual save operation to ensure data size validation.
        """
        pass

    @abstractmethod
    def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        """Retrieve a subscription by ID."""
        pass

    @abstractmethod
    def get_user_subscription(self, user_id: str) -> Optional[Subscription]:
        """Retrieve the active subscription for a user."""
        pass

    @abstractmethod
    def save_usage_record(self, record: UsageRecord) -> None:
        """
        Save a usage record to storage.

        Concrete implementations must call self._validate_and_save_data(record)
        before performing the actual save operation to ensure data size validation.
        """
        pass

    @abstractmethod
    def get_user_usage(
        self, user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[UsageRecord]:
        """Get usage records for a user within a date range."""
        pass

    @abstractmethod
    def save_transaction(self, transaction: PaymentTransaction) -> None:
        """
        Save a payment transaction to storage.

        Concrete implementations must call self._validate_and_save_data(transaction)
        before performing the actual save operation to ensure data size validation.
        """
        pass

    @abstractmethod
    def update_transaction(self, transaction: PaymentTransaction) -> None:
        """
        Update an existing payment transaction in storage.

        Concrete implementations must call self._validate_and_save_data(transaction)
        before performing the actual update operation to ensure data size validation.
        """
        pass

    @abstractmethod
    def get_transaction(self, transaction_id: str) -> Optional[PaymentTransaction]:
        """Retrieve a payment transaction by ID."""
        pass

    @abstractmethod
    def get_transactions_by_user_id(self, user_id: str) -> List[PaymentTransaction]:
        """Retrieve all transactions for a specific user."""
        pass

    @abstractmethod
    def list_transactions(
        self, user_id: Optional[str] = None, status: Optional[str] = None, limit: Optional[int] = None
    ) -> List[PaymentTransaction]:
        """List transactions with optional filtering."""
        pass

    def check_health(self) -> StorageStatus:
        """
        Check the health status of the storage backend.

        Enhanced health check robustness with proper exception handling
        and response time validation to ensure consistent health reporting across storage backends.
        """
        start_time = time.time()
        response_time = None
        error_message = None

        try:
            # Ensure _perform_health_check raises an exception on failure
            # and returns None on success for consistent behavior
            result = self._perform_health_check()

            # Validate that _perform_health_check returns None (success) or raises an exception
            if result is not None:
                logger.warning(
                    "Storage backend %s _perform_health_check returned non-None value: %s. "
                    "Health check methods should return None on success or raise exceptions on failure.",
                    self.name,
                    result,
                )

            # Calculate response time only if health check executed successfully
            response_time = (time.time() - start_time) * 1000

            # Validate response time is reasonable (not negative or excessively large)
            if response_time < 0:
                logger.warning("Storage backend %s reported negative response time: %.2fms", self.name, response_time)
                response_time = 0.0
            elif response_time > 30000:  # 30 seconds
                logger.warning("Storage backend %s reported excessive response time: %.2fms", self.name, response_time)

            self.status = StorageStatus(
                is_healthy=True,
                response_time_ms=response_time,
            )
            logger.debug("Health check passed for storage %s (%.2fms)", self.name, response_time)

        except Exception as e:
            # Capture detailed error information for consistent health reporting
            response_time = (time.time() - start_time) * 1000
            error_message = f"Health check failed: {str(e)}"

            # Log the specific exception type and details
            logger.warning(
                "Health check failed for storage %s (%.2fms): %s (%s)", self.name, response_time, str(e), type(e).__name__
            )

            self.status = StorageStatus(
                is_healthy=False,
                error_message=error_message,
                response_time_ms=response_time,
            )

        return self.status

    @abstractmethod
    def _perform_health_check(self) -> None:
        """
        Perform a health check on the storage backend.

        This method must either:
        - Return None on success (healthy state)
        - Raise an exception on failure (unhealthy state)

        Concrete implementations should perform actual health checks and raise
        StorageError or other appropriate exceptions when health checks fail.
        """
        pass

    def _estimate_data_size(self, obj: Any) -> int:
        """
        Estimate the size of a data object in bytes.

        Args:
            obj: The object to estimate size for (PaymentPlan, Subscription, UsageRecord, PaymentTransaction)

        Returns:
            Estimated size in bytes
        """
        try:
            # Convert object to dictionary and then to JSON string
            if hasattr(obj, "to_dict"):
                data_dict = obj.to_dict()
            else:
                data_dict = obj

            # Serialize to JSON string and get byte length
            json_str = json.dumps(data_dict, default=str, separators=(",", ":"))
            return len(json_str.encode("utf-8"))

        except Exception as e:
            logger.warning("Failed to estimate data size for object %s: %s", type(obj).__name__, e)
            # Fallback: estimate based on object type
            if isinstance(obj, PaymentPlan):
                return 2048  # ~2KB for payment plans
            elif isinstance(obj, Subscription):
                return 1024  # ~1KB for subscriptions
            elif isinstance(obj, UsageRecord):
                return 512  # ~512B for usage records
            elif isinstance(obj, PaymentTransaction):
                return 1536  # ~1.5KB for transactions
            else:
                return 1024  # Default estimate

    def _validate_and_save_data(self, obj: Any) -> None:
        """
        Validate data size before saving to prevent storage failures.

        Args:
            obj: The object to validate and save (PaymentPlan, Subscription, UsageRecord, PaymentTransaction)

        Raises:
            ValidationError: If data size exceeds storage limits
        """
        from ..exceptions import ValidationError

        # Estimate the size of the object
        estimated_size = self._estimate_data_size(obj)

        # Validate against storage backend limits
        if not self.validate_data_size(estimated_size):
            max_size = self.capabilities.max_data_size or "unlimited"
            error_msg = (
                f"Data size ({estimated_size} bytes) exceeds storage backend limit ({max_size} bytes). "
                f"Object type: {type(obj).__name__}"
            )
            logger.error(error_msg)
            raise ValidationError(
                error_msg, field="data_size", value=estimated_size, constraints={"max_size": self.capabilities.max_data_size}
            )

        logger.debug(
            "Data size validation passed for %s: %d bytes (limit: %s)",
            type(obj).__name__,
            estimated_size,
            self.capabilities.max_data_size or "unlimited",
        )

    def get_capabilities(self) -> StorageCapabilities:
        """Get the storage capabilities."""
        return self.capabilities

    def begin_transaction(self) -> Any:
        """
        Begin a transaction for atomic operations.

        Returns:
            Transaction object or context for managing the transaction

        Raises:
            StorageError: If transaction cannot be started or already in progress
        """
        # Default implementation - subclasses should override
        raise StorageError("Transactions not supported by this storage backend")

    def commit(self) -> None:
        """
        Commit the current transaction.

        Raises:
            StorageError: If no transaction is in progress or commit fails
        """
        # Default implementation - subclasses should override
        raise StorageError("Transactions not supported by this storage backend")

    def rollback(self) -> None:
        """
        Rollback the current transaction.

        Raises:
            StorageError: If no transaction is in progress or rollback fails
        """
        # Default implementation - subclasses should override
        raise StorageError("Transactions not supported by this storage backend")

    def supports_transactions(self) -> bool:
        """
        Check if this storage backend supports transactions.

        Returns:
            True if transactions are supported, False otherwise
        """
        return hasattr(self, "begin_transaction") and hasattr(self, "commit") and hasattr(self, "rollback")

    def supports_encryption(self) -> bool:
        """Check if the storage backend supports encryption."""
        return self.capabilities.supports_encryption

    def validate_data_size(self, data_size: int) -> bool:
        """Validate if data size is within limits."""
        if self.capabilities.max_data_size is None:
            return True
        return data_size <= self.capabilities.max_data_size

    def get_storage_info(self) -> Dict[str, Any]:
        """Get comprehensive storage information."""
        return {
            "name": self.name,
            "capabilities": self.capabilities.to_dict(),
            "status": self.status.to_dict(),
        }

    def backup_data(self, backup_path: str) -> None:
        """Backup data if supported."""
        if not self.capabilities.supports_backup:
            raise NotImplementedError(f"{self.name} does not support backup")
        # Subclasses should override this method
        raise NotImplementedError("Backup support not implemented")

    def search_records(self, query: str, record_type: str, limit: Optional[int] = None) -> List[Any]:
        """Search records if supported."""
        if not self.capabilities.supports_search:
            raise NotImplementedError(f"{self.name} does not support search")
        # Subclasses should override this method
        raise NotImplementedError("Search support not implemented")
