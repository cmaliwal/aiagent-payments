"""
Mock payment provider for development and testing.

This module provides a mock payment provider that simulates payment processing
for development and testing purposes. It can be configured to succeed or fail
based on a success rate parameter.
"""

import logging
import random
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from ..exceptions import PaymentFailed, ProviderError
from ..models import PaymentTransaction
from .base import PaymentProvider, ProviderCapabilities

logger = logging.getLogger(__name__)


class MockProvider(PaymentProvider):
    """
    Mock payment provider for development and testing.

    This provider simulates payment processing with configurable success rates.
    It's suitable for development, testing, and prototyping but not for
    production use.
    """

    def __init__(self, success_rate: float = 1.0):
        """
        Initialize the mock payment provider.

        Args:
            success_rate: Probability of successful payments (0.0 to 1.0)
        """
        super().__init__("MockProvider")

        if not 0.0 <= success_rate <= 1.0:
            raise ValueError("Success rate must be between 0.0 and 1.0")

        self.success_rate = success_rate
        self.transactions: dict[str, PaymentTransaction] = {}

        # Critical warning about in-memory storage for beta testers
        logger.warning(
            "MockProvider uses in-memory storage. Transaction data will be lost on restart. "
            "For testing scenarios requiring persistence, use FileStorage or DatabaseStorage. "
            "Success rate: %s",
            success_rate,
        )

    def _get_capabilities(self) -> ProviderCapabilities:
        """
        Get the capabilities of this provider.

        Returns:
            ProviderCapabilities object describing supported features
        """
        return ProviderCapabilities(
            supports_refunds=True,
            supports_webhooks=False,  # Mock provider doesn't support webhooks
            supports_partial_refunds=True,
            supports_subscriptions=True,
            supports_metadata=True,
            supported_currencies=["USD", "EUR", "GBP", "CAD", "AUD"],
            min_amount=0.01,
            max_amount=999999.99,
            processing_time_seconds=0.1,  # Simulated processing time
        )

    def _validate_configuration(self) -> None:
        """
        Validate the provider configuration.

        Mock provider doesn't require external configuration.
        """
        # No external configuration needed for mock provider
        pass

    def _perform_health_check(self) -> None:
        """
        Perform a health check for the mock provider.

        Mock provider is always healthy.
        """
        # Mock provider is always healthy
        pass

    def process_payment(
        self,
        user_id: str,
        amount: float,
        currency: str = "USD",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentTransaction:
        """
        Process a mock payment.

        Args:
            user_id: ID of the user making the payment
            amount: Payment amount
            currency: Payment currency (default: USD)
            metadata: Additional payment metadata

        Returns:
            PaymentTransaction object representing the processed payment

        Raises:
            PaymentFailed: If the payment fails (based on success rate)
            ValidationError: If the payment parameters are invalid
        """
        # Validate payment parameters
        self.validate_payment_parameters(user_id, amount, currency, metadata)

        transaction_id = str(uuid.uuid4())
        now = datetime.now()

        # Simulate processing time
        time.sleep(0.1)

        # Determine success based on success rate
        if random.random() <= self.success_rate:
            status = "completed"
            completed_at = now
            logger.info(
                "Mock payment succeeded: %s for user %s, amount: %.2f %s",
                transaction_id,
                user_id,
                amount,
                currency,
            )
        else:
            status = "failed"
            completed_at = None
            logger.warning(
                "Mock payment failed: %s for user %s, amount: %.2f %s",
                transaction_id,
                user_id,
                amount,
                currency,
            )
            raise PaymentFailed(f"Mock payment failed for transaction {transaction_id}")

        # Create transaction object
        transaction = PaymentTransaction(
            id=transaction_id,
            user_id=user_id,
            amount=amount,
            currency=currency,
            payment_method="mock",
            status=status,
            created_at=now,
            completed_at=completed_at,
            metadata=metadata or {},
        )

        # Store transaction in memory (Mock provider uses in-memory storage only)
        self.transactions[transaction_id] = transaction
        logger.debug("Created mock transaction: %s", transaction_id)

        return transaction

    def _is_dev_mode(self) -> bool:
        """Return True if running in a development or test environment."""
        return super()._is_dev_mode()

    def verify_payment(self, transaction_id: str) -> bool:
        """
        Verify that a mock payment was successfully processed.

        Args:
            transaction_id: ID of the transaction to verify

        Returns:
            True if the payment is verified, False otherwise

        Raises:
            ProviderError: If transaction status is invalid or corrupted
        """
        transaction = self.transactions.get(transaction_id)
        if transaction:
            # Validate transaction status to prevent incorrect simulation
            valid_statuses = ["pending", "completed", "failed", "refunded"]
            if transaction.status not in valid_statuses:
                logger.error(
                    "Invalid transaction status for %s: %s. Expected one of: %s",
                    transaction_id,
                    transaction.status,
                    valid_statuses,
                )
                raise ProviderError(
                    f"Invalid transaction status '{transaction.status}' for transaction {transaction_id}. "
                    f"Expected one of: {valid_statuses}",
                    provider="mock",
                )

            is_verified = transaction.status == "completed"
            logger.debug("Mock payment verification for %s: %s", transaction_id, is_verified)
            return is_verified

        logger.warning("Mock transaction not found: %s", transaction_id)
        return False

    def refund_payment(self, transaction_id: str, amount: Optional[float] = None) -> Any:
        """
        Refund a mock payment or part of a payment.

        Args:
            transaction_id: ID of the transaction to refund
            amount: Amount to refund (None for full refund)

        Returns:
            Refund result from the provider

        Raises:
            ProviderError: If refund fails
        """
        transaction = self.transactions.get(transaction_id)
        if not transaction:
            logger.warning("Mock transaction not found for refund: %s", transaction_id)
            raise ProviderError(f"Transaction {transaction_id} not found", provider="mock")

        if transaction.status != "completed":
            logger.warning("Cannot refund incomplete transaction: %s", transaction_id)
            raise ProviderError(
                f"Cannot refund incomplete transaction {transaction_id}",
                provider="mock",
            )

        try:
            # Simulate processing time
            time.sleep(0.05)

            refund_id = f"re_{transaction_id[:24]}"
            refund_amount = amount if amount is not None else transaction.amount

            # Update transaction status
            transaction.status = "refunded"
            transaction.metadata["mock_refund_id"] = refund_id
            transaction.metadata["refund_amount"] = refund_amount

            logger.info(
                "Mock refund succeeded: %s for transaction %s, amount: %.2f %s",
                refund_id,
                transaction_id,
                refund_amount,
                transaction.currency,
            )

            return {
                "refund_id": refund_id,
                "status": "refunded",
                "amount": refund_amount,
                "currency": transaction.currency,
            }

        except Exception as e:
            logger.error("Error processing mock refund: %s", e)
            raise ProviderError(f"Mock refund error: {e}", provider="mock")

    def get_payment_status(self, transaction_id: str) -> str:
        """
        Get the current status of a mock payment.

        Args:
            transaction_id: ID of the transaction to check

        Returns:
            Payment status string (e.g., 'pending', 'completed', 'failed')

        Raises:
            ProviderError: If status check fails
        """
        transaction = self.transactions.get(transaction_id)
        if transaction:
            logger.debug("Mock payment status for %s: %s", transaction_id, transaction.status)
            return transaction.status

        logger.warning("Mock transaction not found for status: %s", transaction_id)
        raise ProviderError(f"Transaction {transaction_id} not found", provider="mock")

    def create_checkout_session(
        self,
        user_id: str,
        plan: Any,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Create a mock checkout session for payment.

        Args:
            user_id: ID of the user making the payment
            plan: Payment plan or amount information
            success_url: URL to redirect to on successful payment
            cancel_url: URL to redirect to on cancelled payment
            metadata: Additional metadata for the session

        Returns:
            Dictionary containing session information (session_id, checkout_url)
        """
        # Extract amount and currency from plan (for logging purposes)
        if hasattr(plan, "price") and hasattr(plan, "currency"):
            _ = plan.price  # Store for potential future use
            _ = plan.currency  # Store for potential future use
        elif isinstance(plan, dict):
            _ = plan.get("price", 0)  # Store for potential future use
            _ = plan.get("currency", "USD")  # Store for potential future use

        session_id = f"mock_session_{uuid.uuid4().hex[:8]}"

        return {
            "session_id": session_id,
            "checkout_url": success_url,  # Mock provider redirects to success URL
        }

    def health_check(self) -> bool:
        """
        Perform a health check on the mock provider.

        Returns:
            True if the provider is healthy, False otherwise
        """
        return True

    def verify_webhook_signature(self, payload: str, headers: Any) -> bool:
        """
        Verify the signature of a webhook payload.

        Args:
            payload: The webhook payload to verify
            headers: The webhook headers containing signature information

        Returns:
            True if the signature is valid, False otherwise
        """
        # Mock provider always returns True for webhook verification
        return True

    def get_transaction_history(self, user_id: str) -> list[PaymentTransaction]:
        """
        Get transaction history for a user.

        Args:
            user_id: ID of the user

        Returns:
            List of PaymentTransaction objects for the user
        """
        user_transactions = [t for t in self.transactions.values() if t.user_id == user_id]
        logger.debug("Retrieved %d transactions for user %s", len(user_transactions), user_id)
        return user_transactions

    def clear_transactions(self) -> None:
        """
        Clear all stored transactions (useful for testing).
        """
        self.transactions.clear()
        logger.info("Cleared all mock transactions")
