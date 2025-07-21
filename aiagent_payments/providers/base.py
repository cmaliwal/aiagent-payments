"""
Abstract base class for payment providers.

Defines the interface that all payment providers must implement.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models import PaymentTransaction

logger = logging.getLogger(__name__)


@dataclass
class ProviderCapabilities:
    """Represents the capabilities of a payment provider."""

    supports_refunds: bool = True
    supports_webhooks: bool = True
    supports_partial_refunds: bool = True
    supports_subscriptions: bool = True
    supports_metadata: bool = True
    supported_currencies: List[str] = field(default_factory=lambda: ["USD"])
    min_amount: float = 0.01
    max_amount: float = 999999.99
    processing_time_seconds: float = 30.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert capabilities to dictionary."""
        return {
            "supports_refunds": self.supports_refunds,
            "supports_webhooks": self.supports_webhooks,
            "supports_partial_refunds": self.supports_partial_refunds,
            "supports_subscriptions": self.supports_subscriptions,
            "supports_metadata": self.supports_metadata,
            "supported_currencies": self.supported_currencies,
            "min_amount": self.min_amount,
            "max_amount": self.max_amount,
            "processing_time_seconds": self.processing_time_seconds,
        }


@dataclass
class ProviderStatus:
    """Represents the current status of a payment provider."""

    is_healthy: bool = True
    last_check: Optional[datetime] = None
    error_message: Optional[str] = None
    response_time_ms: Optional[float] = None

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
        }


class PaymentProvider(ABC):
    """
    Abstract base class for payment providers.

    Defines the interface that all payment providers must implement.
    """

    def __init__(self, name: str):
        """Initialize the payment provider."""
        self.name = name
        self.capabilities = self._get_capabilities()
        self.status = ProviderStatus()
        self._validate_configuration()
        logger.info("Initialized payment provider: %s", self.name)

    @abstractmethod
    def _get_capabilities(self) -> ProviderCapabilities:
        """Get the capabilities of this provider."""
        pass

    @abstractmethod
    def _validate_configuration(self) -> None:
        """Validate the provider configuration."""
        pass

    @abstractmethod
    def process_payment(
        self,
        user_id: str,
        amount: float,
        currency: str = "USD",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentTransaction:
        """
        Process a payment through this provider.

        Args:
            user_id: ID of the user making the payment
            amount: Payment amount
            currency: Payment currency (default: USD)
            metadata: Additional payment metadata

        Returns:
            PaymentTransaction object representing the processed payment

        Raises:
            PaymentFailed: If the payment processing fails
            ValidationError: If the payment parameters are invalid
        """
        pass

    @abstractmethod
    def verify_payment(self, transaction_id: str) -> bool:
        """
        Verify that a payment was successfully processed.

        Args:
            transaction_id: ID of the transaction to verify

        Returns:
            True if the payment is verified, False otherwise

        Raises:
            ProviderError: If verification fails due to provider issues
        """
        pass

    @abstractmethod
    def refund_payment(self, transaction_id: str, amount: Optional[float] = None) -> Any:
        """
        Refund a payment or part of a payment.

        Args:
            transaction_id: ID of the transaction to refund
            amount: Amount to refund (None for full refund)

        Returns:
            Refund result from the provider

        Raises:
            ProviderError: If refund fails due to provider issues
            ValidationError: If refund parameters are invalid
        """
        pass

    @abstractmethod
    def get_payment_status(self, transaction_id: str) -> str:
        """
        Get the current status of a payment.

        Args:
            transaction_id: ID of the transaction to check

        Returns:
            Payment status string (e.g., 'pending', 'completed', 'failed')

        Raises:
            ProviderError: If status check fails due to provider issues
        """
        pass

    @abstractmethod
    def verify_webhook_signature(self, payload: str, headers: Any) -> bool:
        """
        Verify the signature of a webhook payload.

        Args:
            payload: The webhook payload to verify
            headers: The webhook headers containing signature information

        Returns:
            True if the signature is valid, False otherwise

        Raises:
            ProviderError: If verification fails due to provider issues
        """
        pass

    @abstractmethod
    def create_checkout_session(
        self,
        user_id: str,
        plan: Any,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Create a checkout session for payment.

        Args:
            user_id: ID of the user making the payment
            plan: Payment plan or amount information
            success_url: URL to redirect to on successful payment
            cancel_url: URL to redirect to on cancelled payment
            metadata: Additional metadata for the session

        Returns:
            Dictionary containing session information (e.g., session_id, checkout_url)

        Raises:
            ProviderError: If session creation fails
            ValidationError: If parameters are invalid
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Perform a health check on the provider.

        Returns:
            True if the provider is healthy, False otherwise
        """
        pass

    def check_health(self) -> ProviderStatus:
        """
        Check the health status of the provider.

        Enhanced health check robustness with proper exception handling
        and response time validation to ensure consistent health reporting across providers.
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
                    "Provider %s _perform_health_check returned non-None value: %s. "
                    "Health check methods should return None on success or raise exceptions on failure.",
                    self.name,
                    result,
                )

            # Calculate response time only if health check executed successfully
            response_time = (time.time() - start_time) * 1000

            # Validate response time is reasonable (not negative or excessively large)
            if response_time < 0:
                logger.warning("Provider %s reported negative response time: %.2fms", self.name, response_time)
                response_time = 0.0
            elif response_time > 30000:  # 30 seconds
                logger.warning("Provider %s reported excessive response time: %.2fms", self.name, response_time)

            self.status = ProviderStatus(
                is_healthy=True,
                response_time_ms=response_time,
            )
            logger.debug("Health check passed for provider %s (%.2fms)", self.name, response_time)

        except Exception as e:
            # Capture detailed error information for consistent health reporting
            response_time = (time.time() - start_time) * 1000
            error_message = f"Health check failed: {str(e)}"

            # Log the specific exception type and details
            logger.warning(
                "Health check failed for provider %s (%.2fms): %s (%s)", self.name, response_time, str(e), type(e).__name__
            )

            self.status = ProviderStatus(
                is_healthy=False,
                error_message=error_message,
                response_time_ms=response_time,
            )

        return self.status

    @abstractmethod
    def _perform_health_check(self) -> None:
        """
        Perform a health check on the provider.

        This method must either:
        - Return None on success (healthy state)
        - Raise an exception on failure (unhealthy state)

        Concrete implementations should perform actual health checks and raise
        ProviderError or other appropriate exceptions when health checks fail.
        """
        pass

    def get_capabilities(self) -> ProviderCapabilities:
        """Get the provider capabilities."""
        return self.capabilities

    def supports_currency(self, currency: str) -> bool:
        """Check if the provider supports a specific currency."""
        return currency in self.capabilities.supported_currencies

    def supports_amount(self, amount: float) -> bool:
        """Check if the provider supports a specific amount."""
        return self.capabilities.min_amount <= amount <= self.capabilities.max_amount

    def _validate_metadata_structure(self, metadata: Dict[str, Any], max_depth: int = 3) -> None:
        """
        Validate metadata structure and content for data integrity.

        Args:
            metadata: The metadata dictionary to validate
            max_depth: Maximum nesting depth allowed

        Raises:
            ValidationError: If metadata structure is invalid
        """
        from ..exceptions import ValidationError

        if not metadata:
            return

        # Validate metadata size constraints
        if len(metadata) > 100:
            raise ValidationError(
                f"Metadata contains too many keys ({len(metadata)}). Maximum allowed: 100",
                field="metadata",
                value=f"dict with {len(metadata)} keys",
                constraints={"max_keys": 100},
            )

        def _validate_value(value: Any, depth: int, path: str) -> None:
            """Recursively validate metadata values."""
            if depth > max_depth:
                raise ValidationError(
                    f"Metadata nesting too deep at path '{path}'. Maximum depth: {max_depth}",
                    field="metadata",
                    value=f"nested structure at {path}",
                    constraints={"max_depth": max_depth},
                )

            if isinstance(value, dict):
                if len(value) > 50:  # Limit nested dict size
                    raise ValidationError(
                        f"Nested metadata at '{path}' contains too many keys ({len(value)}). Maximum allowed: 50",
                        field="metadata",
                        value=f"nested dict with {len(value)} keys",
                        constraints={"max_nested_keys": 50},
                    )
                for k, v in value.items():
                    _validate_value(v, depth + 1, f"{path}.{k}")
            elif isinstance(value, (list, tuple)):
                if len(value) > 100:  # Limit list size
                    raise ValidationError(
                        f"Metadata list at '{path}' too large ({len(value)}). Maximum allowed: 100",
                        field="metadata",
                        value=f"list with {len(value)} items",
                        constraints={"max_list_size": 100},
                    )
                for i, item in enumerate(value):
                    _validate_value(item, depth + 1, f"{path}[{i}]")
            elif not isinstance(value, (str, int, float, bool, type(None))):
                raise ValidationError(
                    f"Invalid metadata value type at '{path}': {type(value).__name__}. "
                    f"Allowed types: str, int, float, bool, None, dict, list",
                    field="metadata",
                    value=f"{type(value).__name__} at {path}",
                    constraints={"allowed_types": ["str", "int", "float", "bool", "None", "dict", "list"]},
                )

        # Validate each metadata key and value
        for key, value in metadata.items():
            # Validate key type and length
            if not isinstance(key, str):
                raise ValidationError(
                    f"Metadata key must be a string, got {type(key).__name__}",
                    field="metadata",
                    value=f"key: {type(key).__name__}",
                    constraints={"key_type": "str"},
                )

            if len(key) > 100:
                raise ValidationError(
                    f"Metadata key too long: '{key}' ({len(key)} chars). Maximum allowed: 100",
                    field="metadata",
                    value=f"key: {key[:50]}...",
                    constraints={"max_key_length": 100},
                )

            # Validate value structure
            _validate_value(value, 1, key)

    def validate_payment_parameters(
        self,
        user_id: str,
        amount: float,
        currency: str = "USD",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Validate payment parameters before processing.

        Enhanced metadata validation with comprehensive structure
        and content validation to ensure data integrity during beta testing.
        """
        from ..exceptions import ValidationError

        if not user_id or not isinstance(user_id, str):
            raise ValidationError("user_id must be a non-empty string", field="user_id", value=user_id)

        if not self.supports_amount(amount):
            raise ValidationError(
                f"Amount {amount} is not supported by {self.name}",
                field="amount",
                value=amount,
                constraints={"min": self.capabilities.min_amount, "max": self.capabilities.max_amount},
            )

        if not self.supports_currency(currency):
            raise ValidationError(
                f"Currency {currency} is not supported by {self.name}",
                field="currency",
                value=currency,
                constraints={"supported": self.capabilities.supported_currencies},
            )

        # Enhanced metadata validation
        if metadata is not None:
            if not isinstance(metadata, dict):
                raise ValidationError("metadata must be a dictionary", field="metadata", value=metadata)

            # Validate metadata structure and content
            self._validate_metadata_structure(metadata)

    def get_provider_info(self) -> Dict[str, Any]:
        """Get comprehensive provider information."""
        return {
            "name": self.name,
            "capabilities": self.capabilities.to_dict(),
            "status": self.status.to_dict(),
        }

    def _is_dev_mode(self) -> bool:
        """
        Return True if running in a development or test environment.

        Standardized environment detection across all providers.
        Checks multiple environment variables for compatibility.
        """
        import os
        import sys

        # Check multiple environment variables for compatibility
        env_vars = [
            os.environ.get("AIAgentPayments_DevMode"),
            os.environ.get("AIA_PAYMENTS_ENV"),
            os.environ.get("AIAgentPayments_Environment"),
        ]

        # Check for dev/test indicators in environment variables
        for env_var in env_vars:
            if env_var and env_var.lower() in {"1", "true", "dev", "development", "test", "testing"}:
                return True

        # Check for pytest or CI environment
        if os.environ.get("PYTEST_CURRENT_TEST") is not None:
            return True

        if os.environ.get("CI") == "true":
            return True

        # Check command line arguments for pytest
        if any("pytest" in arg for arg in sys.argv):
            return True

        return False

    def _validate_metadata(self, metadata):
        """Validate metadata to ensure it's a dictionary or None."""
        from ..exceptions import ValidationError

        if metadata is not None and not isinstance(metadata, dict):
            raise ValidationError(
                f"Metadata must be a dictionary or None, got {type(metadata).__name__}",
                field="metadata",
                value=metadata,
            )

    def _generate_unique_transaction_id(self, max_attempts: int = 10) -> str:
        """
        Generate a unique transaction ID with thread-safe collision detection and reservation.

        This method prevents race conditions by checking storage first (source of truth),
        then using a lock to check and reserve the ID in cache before returning.
        A '__RESERVED__' placeholder is inserted in cache to mark the ID as in use.
        If reservation fails (e.g., storage or transaction creation fails), the placeholder is removed.

        Args:
            max_attempts: Maximum number of attempts to generate unique ID

        Returns:
            Unique transaction ID string

        Raises:
            ProviderError: If unable to generate unique ID after max attempts
        """
        import uuid

        from ..exceptions import ProviderError

        for attempt in range(max_attempts):
            transaction_id = str(uuid.uuid4())

            # 1. Check storage first (source of truth)
            try:
                if self.storage.get_transaction(transaction_id):
                    continue
            except Exception as storage_error:
                logger.warning(f"Storage check failed: {storage_error}")
                continue

            # 2. If using a lock, acquire it for cache and reservation
            if hasattr(self, "transactions_lock"):
                with self.transactions_lock:
                    # 2a. If cache exists, check and reserve
                    if hasattr(self, "transactions"):
                        if transaction_id in self.transactions:
                            continue
                        # Reserve in cache (insert a placeholder)
                        self.transactions[transaction_id] = "__RESERVED__"
                        # Double-check storage after reservation to avoid race
                        try:
                            if not self.storage.get_transaction(transaction_id):
                                return transaction_id
                        except Exception as storage_error:
                            logger.warning(f"Storage check failed after reservation: {storage_error}")
                        # Roll back reservation if storage check fails
                        self.transactions.pop(transaction_id, None)
                        continue
                    else:
                        return transaction_id
            else:
                # No lock, fallback to cache check
                if hasattr(self, "transactions"):
                    if transaction_id in self.transactions:
                        continue
                    self.transactions[transaction_id] = "__RESERVED__"
                    try:
                        if not self.storage.get_transaction(transaction_id):
                            return transaction_id
                    except Exception as storage_error:
                        logger.warning(f"Storage check failed after reservation: {storage_error}")
                    self.transactions.pop(transaction_id, None)
                    continue
                else:
                    return transaction_id

        raise ProviderError(f"Failed to generate unique transaction ID after {max_attempts} attempts", provider=self.name)

    def _handle_storage_failure(self, transaction, storage_error, operation="save"):
        """
        Handle storage failures consistently across all providers.

        Args:
            transaction: The transaction that failed to save
            storage_error: The storage error that occurred
            operation: The operation that failed (save, update, etc.)

        Returns:
            bool: True if the operation should continue, False if it should fail
        """
        logger.error(f"Failed to {operation} transaction to storage: {storage_error}")

        # For production environments, log critical storage failure but don't fail payment
        if not self._is_dev_mode():
            logger.critical(
                f"CRITICAL: Payment succeeded but storage failed for transaction {transaction.id}. "
                f"Payment amount: {transaction.amount} {transaction.currency}"
            )
            # Add storage failure flag to transaction metadata
            transaction.metadata["storage_failed"] = True
            transaction.metadata["storage_error"] = str(storage_error)
            transaction.metadata["storage_operation"] = operation
            # Notify monitoring system (log for now)
            self._notify_storage_failure(transaction, storage_error, operation)
            return True  # Continue with cached transaction
        else:
            # For mock/dev environments, continue with cached transaction
            logger.warning(f"Continuing with cached transaction due to storage failure (mock/dev mode)")
            return True  # Continue with cached transaction

    def _notify_storage_failure(self, transaction, storage_error, operation):
        """
        Notify monitoring/ops of a storage failure. For now, just logs, but can be extended.
        """
        import json
        from datetime import datetime, timezone

        alert_data = {
            "transaction_id": getattr(transaction, "id", None),
            "amount": getattr(transaction, "amount", None),
            "currency": getattr(transaction, "currency", None),
            "error": str(storage_error),
            "operation": operation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"[ALERT] Storage failure: {json.dumps(alert_data)}")

    def _cleanup_reserved_placeholder(self, transaction_id: str):
        """
        Clean up a __RESERVED__ placeholder from the transactions cache.

        This method should be called when a transaction creation fails after
        a placeholder has been reserved, to prevent cache pollution.

        Args:
            transaction_id: The transaction ID to clean up
        """
        if hasattr(self, "transactions") and hasattr(self, "transactions_lock"):
            with self.transactions_lock:
                if transaction_id in self.transactions and self.transactions[transaction_id] == "__RESERVED__":
                    self.transactions.pop(transaction_id, None)
                    logger.debug(f"Cleaned up __RESERVED__ placeholder for transaction {transaction_id}")
        elif hasattr(self, "transactions"):
            # Fallback for providers without lock
            if transaction_id in self.transactions and self.transactions[transaction_id] == "__RESERVED__":
                self.transactions.pop(transaction_id, None)
                logger.debug(f"Cleaned up __RESERVED__ placeholder for transaction {transaction_id} (no lock)")

    def _cleanup_all_reserved_placeholders(self):
        """
        Clean up all __RESERVED__ placeholders from the transactions cache.

        This method can be used for maintenance or debugging purposes.
        """
        if not hasattr(self, "transactions"):
            return

        cleaned_count = 0
        if hasattr(self, "transactions_lock"):
            with self.transactions_lock:
                reserved_ids = [tx_id for tx_id, tx in self.transactions.items() if tx == "__RESERVED__"]
                for tx_id in reserved_ids:
                    self.transactions.pop(tx_id, None)
                    cleaned_count += 1
        else:
            # Fallback for providers without lock
            reserved_ids = [tx_id for tx_id, tx in self.transactions.items() if tx == "__RESERVED__"]
            for tx_id in reserved_ids:
                self.transactions.pop(tx_id, None)
                cleaned_count += 1

        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} __RESERVED__ placeholders from transactions cache")
