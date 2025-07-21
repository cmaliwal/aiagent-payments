"""
Stripe payment provider for the AI Agent Payments SDK.
"""

import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from aiagent_payments.storage import MemoryStorage, StorageBackend

from ..config import MINIMUM_AMOUNTS, SUPPORTED_CURRENCIES
from ..exceptions import ConfigurationError, PaymentFailed, ProviderError, ValidationError
from ..models import PaymentPlan, PaymentTransaction, PaymentType
from ..utils import retry
from .base import PaymentProvider

logger = logging.getLogger(__name__)


class StripeProvider(PaymentProvider):
    """
    Stripe payment provider.

    Note: The in-memory transactions cache (self.transactions) stores only PaymentTransaction objects
    from process_payment, process_stablecoin_payment, refund_payment, verify_payment, and
    verify_stablecoin_payment. Checkout sessions and customer-related data are stored in self.storage
    but not cached in self.transactions to avoid confusion and maintain clear separation of concerns.
    """

    # TODO: Add support for multiple Stripe accounts and regions
    # TODO: Add Stripe Connect support for marketplace scenarios
    def __init__(self, api_key: str | None = None, webhook_secret: str | None = None, storage: StorageBackend | None = None):
        self.api_key = api_key or os.getenv("STRIPE_API_KEY")
        self.webhook_secret = webhook_secret or os.getenv("STRIPE_WEBHOOK_SECRET")
        self.storage = storage or MemoryStorage()
        self.transactions: dict[str, PaymentTransaction] = {}  # In-memory transaction cache
        self.transactions_lock = threading.Lock()  # Thread-safe lock for cache updates
        super().__init__("StripeProvider")
        try:
            import stripe  # type: ignore

            stripe.api_key = self.api_key  # type: ignore[attr-defined]
            self._stripe_available = True
            logger.info("StripeProvider initialized.")
        except ImportError:
            self._stripe_available = False
            logger.warning("Stripe library not installed. Install with: pip install stripe")
            logger.info("StripeProvider initialized in mock mode")

    def _validate_metadata(self, metadata):
        """Validate metadata is a dict if provided."""
        super()._validate_metadata(metadata)

    def _is_dev_mode(self) -> bool:
        """Return True if running in a development or test environment."""
        return super()._is_dev_mode()

    def _get_capabilities(self):
        """
        Get the capabilities of this provider.
        Returns:
            ProviderCapabilities object describing supported features
        """
        from .base import ProviderCapabilities

        return ProviderCapabilities(
            supports_refunds=True,
            supports_webhooks=True,
            supports_partial_refunds=True,
            supports_subscriptions=True,
            supports_metadata=True,
            supported_currencies=["USD", "EUR", "GBP", "CAD", "AUD"],
            min_amount=0.5,
            max_amount=1000000.0,
            processing_time_seconds=2.0,
        )

    def _validate_configuration(self):
        """
        Validate the provider configuration.
        Raises:
            ConfigurationError: If the configuration is invalid
        """
        if not self.api_key or not isinstance(self.api_key, str):
            raise ConfigurationError("Stripe API key is required for StripeProvider.")
        # Optionally validate webhook_secret if webhooks are used

    def _perform_health_check(self):
        """
        Perform a health check for the Stripe provider.
        Raises:
            Exception: If the health check fails
        """
        try:
            if not self._stripe_available:
                raise Exception("stripe library not available. Cannot perform health check.")
            import stripe

            stripe.api_key = self.api_key
            # Try to retrieve account info first (works with most API keys)
            try:
                account = getattr(stripe, "Account").retrieve()
                if not account or not getattr(account, "id", None):
                    raise Exception("Stripe account info could not be retrieved.")
            except Exception:
                # Fallback: try to retrieve balance (works with restricted keys)
                try:
                    balance = getattr(stripe, "Balance").retrieve()
                    if not balance:
                        raise Exception("Stripe balance could not be retrieved.")
                except Exception:
                    # Final fallback: try to create a test payment intent (minimal operation)
                    try:
                        test_intent = stripe.PaymentIntent.create(
                            amount=100,  # $1.00
                            currency="usd",
                            description="Health check test",
                            metadata={"health_check": "true"},
                        )
                        if not test_intent or not test_intent.id:
                            raise Exception("Stripe test payment intent could not be created.")

                        # Health check passes if PaymentIntent creation succeeds
                        # Try to cancel the test intent for cleanup, but don't fail if cancellation fails
                        try:
                            stripe.PaymentIntent.cancel(test_intent.id)
                            logger.debug("Successfully cancelled test PaymentIntent for health check cleanup")
                        except Exception as cancel_error:
                            logger.warning(f"Failed to cancel test PaymentIntent during health check cleanup: {cancel_error}")
                            # Don't raise - the health check should still pass since creation succeeded

                    except Exception as e:
                        raise Exception(f"All Stripe health check methods failed: {e}")
        except Exception as e:
            raise Exception(f"Stripe health check failed: {e}")

    def _validate_payment_intent_id(self, payment_intent_id: str) -> bool:
        """
        Validate the format of a Stripe PaymentIntent ID.

        Args:
            payment_intent_id: The PaymentIntent ID to validate

        Returns:
            bool: True if valid, False otherwise
        """
        if not payment_intent_id or not isinstance(payment_intent_id, str):
            return False
        if not payment_intent_id.startswith("pi_"):
            return False
        return True

    @retry(
        exceptions=Exception,
        max_attempts=3,
        logger=logger,
        retry_message="Retrying Stripe payment...",
    )
    def process_payment(
        self,
        user_id: str,
        amount: float,
        currency: str = "USD",
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> PaymentTransaction:
        """
        Process a payment using Stripe.

        Args:
            user_id: Unique identifier for the user
            amount: Payment amount
            currency: Currency code (default: USD)
            metadata: Optional additional metadata
            idempotency_key: Optional idempotency key for the request

        Returns:
            PaymentTransaction: The payment transaction

        Raises:
            ValidationError: If parameters are invalid
            PaymentFailed: If payment processing fails
        """
        if not user_id or not isinstance(user_id, str):
            raise ValidationError("Invalid user_id", field="user_id", value=user_id)
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValidationError("Amount must be positive", field="amount", value=amount)
        if not currency or not isinstance(currency, str):
            raise ValidationError("Invalid currency", field="currency", value=currency)

        # Validate currency and amount
        if currency.upper() not in SUPPORTED_CURRENCIES:
            raise ValidationError(
                f"Currency {currency} is not supported. Supported currencies: {', '.join(sorted(SUPPORTED_CURRENCIES))}",
                field="currency",
                value=currency,
            )
        # Validate minimum amount for stablecoins
        if currency.upper() in MINIMUM_AMOUNTS:
            min_amount = MINIMUM_AMOUNTS[currency.upper()]
            if amount < min_amount:
                raise ValidationError(
                    f"Amount {amount} {currency} is below the minimum {min_amount} {currency}", field="amount", value=amount
                )

        # Validate metadata to prevent TypeError in dictionary unpacking
        self._validate_metadata(metadata)

        try:
            # Check if we're in mock mode or if stripe library is not available
            if not self._stripe_available:
                # Only create mock transactions in development/testing environments
                if self._is_dev_mode():
                    # Generate unique transaction ID for mock mode
                    transaction_id = self._generate_unique_transaction_id()

                    now = datetime.now(timezone.utc)
                    transaction = PaymentTransaction(
                        id=transaction_id,
                        user_id=user_id,
                        amount=amount,
                        currency=currency,
                        payment_method="stripe",
                        status="completed",
                        created_at=now,
                        completed_at=now,
                        metadata={
                            **(metadata or {}),
                            "stripe_payment_intent_id": f"mock_pi_{uuid.uuid4().hex[:8]}",
                            "stripe_status": "succeeded",
                            "mock_transaction": True,
                        },
                    )

                    # Save transaction atomically with cache update
                    with self.transactions_lock:
                        self.transactions[transaction_id] = transaction
                        try:
                            self.storage.save_transaction(transaction)
                            logger.info(
                                f"Mock Stripe payment processed: {transaction_id} for user {user_id}, amount: {amount} {currency}"
                            )
                        except Exception as storage_error:
                            logger.error(f"Failed to save mock transaction to storage: {storage_error}")
                            # Continue with cached transaction if storage fails

                    # Return the transaction we just saved (avoid race condition with get_transaction)
                    return transaction
                else:
                    # In production, fail fast if Stripe library is not available
                    raise ProviderError(
                        "stripe library not available. Cannot process Stripe payments in production.", provider="stripe"
                    )

            import stripe  # type: ignore

            stripe.api_key = self.api_key  # type: ignore[attr-defined]
            idempotency_key = idempotency_key or str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{user_id}-{amount}-{currency}"))

            logger.info(f"Processing payment for user {user_id}: amount={amount}, currency={currency}")

            # Create a PaymentIntent
            payment_intent_data = {
                "amount": int(amount * 100),  # Convert to cents
                "currency": currency.lower(),
                "metadata": {
                    **(metadata or {}),
                    "user_id": user_id,
                    "idempotency_key": idempotency_key,
                },
            }

            payment_intent = stripe.PaymentIntent.create(**payment_intent_data)  # type: ignore[attr-defined]

            # Generate unique transaction ID with storage check to prevent duplicates
            transaction_id = self._generate_unique_transaction_id()
            now = datetime.now(timezone.utc)
            status = payment_intent.status

            # Map Stripe statuses to our allowed statuses
            if status == "succeeded":
                mapped_status = "completed"
                completed_at = now
            elif status in ["requires_payment_method", "requires_confirmation", "requires_action", "processing"]:
                mapped_status = "pending"
                completed_at = None
            elif status == "canceled":
                mapped_status = "cancelled"
                completed_at = None
            else:
                mapped_status = "failed"
                completed_at = None

            transaction = PaymentTransaction(
                id=transaction_id,  # Use the generated transaction_id
                user_id=user_id,
                amount=amount,
                currency=currency,
                payment_method="stripe",
                status=mapped_status,
                created_at=now,
                completed_at=completed_at,
                metadata={
                    **(metadata or {}),
                    "stripe_payment_intent_id": payment_intent.id,
                    "stripe_status": status,  # Keep original Stripe status for reference
                },
            )
            # Save transaction atomically with cache update
            with self.transactions_lock:
                self.transactions[transaction_id] = transaction
                try:
                    self.storage.save_transaction(transaction)
                    logger.info(
                        "Stripe payment processed: "
                        + transaction_id
                        + " for user "
                        + user_id
                        + ", amount: "
                        + str(amount)
                        + " "
                        + currency
                        + ", status: "
                        + status
                    )
                except Exception as storage_error:
                    logger.error(f"Failed to save transaction to storage: {storage_error}")
                    # For production environments, log critical storage failure but don't fail payment
                    if not self._is_dev_mode():
                        logger.critical(
                            f"CRITICAL: Payment succeeded but storage failed for transaction {transaction_id}. Payment amount: {amount} {currency}"
                        )
                        # Add storage failure flag to transaction metadata
                        transaction.metadata["storage_failed"] = True
                        transaction.metadata["storage_error"] = str(storage_error)
                    # For mock/dev environments, continue with cached transaction
                    else:
                        logger.warning("Continuing with cached transaction due to storage failure (mock/dev mode)")

            # Return the transaction we just saved (avoid race condition with get_transaction)
            # Payment succeeded regardless of storage status
            return transaction

        except Exception as e:
            logger.error(f"Error processing Stripe payment: {e}")
            # Clean up any __RESERVED__ placeholder if transaction creation failed
            if "transaction_id" in locals():
                self._cleanup_reserved_placeholder(transaction_id)
            raise PaymentFailed(f"Stripe payment processing error: {e}")

    @retry(
        exceptions=Exception,
        max_attempts=3,
        logger=logger,
        retry_message="Retrying Stripe payment verification...",
    )
    def verify_payment(self, transaction_id: str) -> bool:
        """Verify the status of a Stripe payment."""
        if not transaction_id or not isinstance(transaction_id, str):
            raise ValidationError("Invalid transaction_id", field="transaction_id", value=transaction_id)
        transaction = self.storage.get_transaction(transaction_id)
        if not transaction:
            logger.warning("Stripe transaction not found: " + transaction_id)
            return False
        try:
            if not self._stripe_available:
                if self._is_dev_mode():
                    logger.info(f"Mock verify Stripe payment: {transaction_id}")
                    return True
                else:
                    raise ProviderError("stripe library not available. Cannot verify Stripe payments.", provider="stripe")
            import stripe

            stripe.api_key = self.api_key  # type: ignore[attr-defined]
            payment_intent_id = transaction.metadata.get("stripe_payment_intent_id")
            if not payment_intent_id:
                logger.warning("No Stripe PaymentIntent ID in transaction metadata: " + transaction_id)
                return False
            payment_intent = getattr(stripe, "PaymentIntent").retrieve(payment_intent_id)
            is_verified = payment_intent.status == "succeeded"
            logger.debug("Stripe payment verification for " + transaction_id + ": " + str(is_verified))

            # Map Stripe status to our internal status
            status_mapping = {
                "succeeded": "completed",
                "processing": "pending",
                "requires_payment_method": "pending",
                "requires_confirmation": "pending",
                "requires_action": "pending",
                "canceled": "cancelled",
                "failed": "failed",
            }
            mapped_status = status_mapping.get(payment_intent.status, "pending")
            transaction.status = mapped_status
            # Update transaction in cache and storage without changing ID
            with self.transactions_lock:
                self.transactions[transaction.id] = transaction
            self.storage.save_transaction(transaction)
            return is_verified
        except ImportError:
            logger.warning("Stripe library not installed. Falling back to mock mode.")
            return super().verify_payment(transaction_id)
        except Exception as e:
            logger.error("Error verifying Stripe payment: " + str(e))
            raise ProviderError("Stripe payment verification error: " + str(e), provider="stripe")

    def verify_webhook_signature(self, payload: str, sig_header: str) -> bool:
        """
        Verify the signature of a Stripe webhook payload.

        Args:
            payload: The webhook payload to verify
            sig_header: The webhook signature header

        Returns:
            True if the signature is valid, False otherwise
        """
        try:
            if not self.webhook_secret:
                logger.warning("No webhook secret configured for Stripe")
                return False

            import stripe

            # Verify the webhook signature
            event = stripe.Webhook.construct_event(payload, sig_header, self.webhook_secret)
            logger.debug(f"Stripe webhook signature verified for event: {event.get('type')}")
            return True
        except ImportError:
            logger.warning("stripe library not available for webhook verification")
            return False
        except Exception as e:
            logger.error(f"Stripe webhook signature verification failed: {e}")
            return False

    def handle_webhook(self, payload: str, sig_header: str) -> None:
        """
        Handle Stripe webhook events and update transaction statuses.

        This method processes webhook events from Stripe and updates the corresponding
        PaymentTransaction records in storage. It handles checkout.session.completed
        events to update pending transactions to completed status.

        Args:
            payload: The webhook payload from Stripe
            sig_header: The webhook signature header

        Raises:
            ProviderError: If webhook signature is invalid or processing fails
        """
        if not self.verify_webhook_signature(payload, sig_header):
            raise ProviderError("Invalid webhook signature", provider="stripe")

        try:
            import stripe

            event = stripe.Webhook.construct_event(payload, sig_header, self.webhook_secret)
            event_type = event.get("type")

            if event_type == "checkout.session.completed":
                session = event["data"]["object"]
                session_id = session.get("id")

                # Find the pending transaction for this session
                all_transactions = self.storage.list_transactions() if hasattr(self.storage, "list_transactions") else []
                pending_transaction = None

                for tx in all_transactions:
                    if (
                        tx.metadata.get("stripe_checkout_session_id") == session_id
                        and tx.status == "pending"
                        and tx.payment_method == "stripe_checkout"
                    ):
                        pending_transaction = tx
                        break

                if pending_transaction:
                    # Update the transaction to completed status
                    pending_transaction.status = "completed"
                    pending_transaction.completed_at = datetime.now(timezone.utc)

                    # Add additional metadata from the session
                    pending_transaction.metadata.update(
                        {
                            "stripe_payment_intent_id": session.get("payment_intent"),
                            "stripe_customer_id": session.get("customer"),
                            "webhook_processed": True,
                            "webhook_event_id": event.get("id"),
                        }
                    )

                    # Update in cache and storage
                    with self.transactions_lock:
                        self.transactions[pending_transaction.id] = pending_transaction

                    try:
                        self.storage.save_transaction(pending_transaction)
                        logger.info(
                            f"Webhook processed: Updated transaction {pending_transaction.id} to completed for checkout session {session_id}"
                        )
                    except Exception as storage_error:
                        logger.error(f"Failed to save completed transaction to storage: {storage_error}")
                        # Do not raise ProviderError, just log and return
                        return
                else:
                    logger.warning(f"No pending transaction found for checkout session {session_id}")

                    # Create a new transaction if none exists (fallback)
                    session_metadata = session.get("metadata", {})
                    user_id = session_metadata.get("user_id") if isinstance(session_metadata, dict) else None
                    if user_id:
                        transaction_id = str(uuid.uuid4())
                        now = datetime.now(timezone.utc)
                        amount = session.get("amount_total", 0) / 100.0
                        currency = session.get("currency", "usd").upper()

                        transaction = PaymentTransaction(
                            id=transaction_id,
                            user_id=user_id,
                            amount=amount,
                            currency=currency,
                            payment_method="stripe_checkout",
                            status="completed",
                            created_at=now,
                            completed_at=now,
                            metadata={
                                "stripe_checkout_session_id": session_id,
                                "stripe_payment_intent_id": session.get("payment_intent"),
                                "stripe_customer_id": session.get("customer"),
                                "webhook_created": True,
                                "webhook_event_id": event.get("id"),
                            },
                        )

                        with self.transactions_lock:
                            self.transactions[transaction_id] = transaction

                        try:
                            self.storage.save_transaction(transaction)
                            logger.info(
                                f"Webhook fallback: Created transaction {transaction_id} for checkout session {session_id}"
                            )
                        except Exception as storage_error:
                            logger.error(f"Failed to save webhook-created transaction to storage: {storage_error}")

            elif event_type == "checkout.session.expired":
                session = event["data"]["object"]
                session_id = session.get("id")

                # Find and update pending transactions to expired status
                all_transactions = self.storage.list_transactions() if hasattr(self.storage, "list_transactions") else []

                for tx in all_transactions:
                    if (
                        tx.metadata.get("stripe_checkout_session_id") == session_id
                        and tx.status == "pending"
                        and tx.payment_method == "stripe_checkout"
                    ):

                        tx.status = "expired"
                        tx.metadata.update(
                            {
                                "webhook_processed": True,
                                "webhook_event_id": event.get("id"),
                            }
                        )

                        with self.transactions_lock:
                            self.transactions[tx.id] = tx

                        try:
                            self.storage.save_transaction(tx)
                            logger.info(
                                f"Webhook processed: Updated transaction {tx.id} to expired for checkout session {session_id}"
                            )
                        except Exception as storage_error:
                            logger.error(f"Failed to save expired transaction to storage: {storage_error}")
                            # Do not raise ProviderError, just log and continue

            elif event_type == "payment_intent.succeeded":
                payment_intent = event["data"]["object"]
                payment_intent_id = payment_intent.get("id")

                # Find transactions for this payment intent
                all_transactions = self.storage.list_transactions() if hasattr(self.storage, "list_transactions") else []

                for tx in all_transactions:
                    if tx.metadata.get("stripe_payment_intent_id") == payment_intent_id and tx.status in [
                        "pending",
                        "processing",
                    ]:

                        tx.status = "completed"
                        tx.completed_at = datetime.now(timezone.utc)
                        tx.metadata.update(
                            {
                                "webhook_processed": True,
                                "webhook_event_id": event.get("id"),
                            }
                        )

                        with self.transactions_lock:
                            self.transactions[tx.id] = tx

                        try:
                            self.storage.save_transaction(tx)
                            logger.info(
                                f"Webhook processed: Updated transaction {tx.id} to completed for payment intent {payment_intent_id}"
                            )
                        except Exception as storage_error:
                            logger.error(f"Failed to save completed transaction to storage: {storage_error}")
                            # Do not raise ProviderError, just log and continue

            elif event_type == "payment_intent.payment_failed":
                payment_intent = event["data"]["object"]
                payment_intent_id = payment_intent.get("id")

                # Find transactions for this payment intent
                all_transactions = self.storage.list_transactions() if hasattr(self.storage, "list_transactions") else []

                for tx in all_transactions:
                    if tx.metadata.get("stripe_payment_intent_id") == payment_intent_id and tx.status in [
                        "pending",
                        "processing",
                    ]:

                        tx.status = "failed"
                        tx.metadata.update(
                            {
                                "webhook_processed": True,
                                "webhook_event_id": event.get("id"),
                                "failure_reason": payment_intent.get("last_payment_error", {}).get("message", "Unknown error"),
                            }
                        )

                        with self.transactions_lock:
                            self.transactions[tx.id] = tx

                        try:
                            self.storage.save_transaction(tx)
                            logger.info(
                                f"Webhook processed: Updated transaction {tx.id} to failed for payment intent {payment_intent_id}"
                            )
                        except Exception as storage_error:
                            logger.error(f"Failed to save failed transaction to storage: {storage_error}")
                            # Do not raise ProviderError, just log and continue

            else:
                logger.debug(f"Unhandled Stripe webhook event type: {event_type}")

        except ImportError:
            logger.warning("stripe library not available for webhook processing")
            raise ProviderError("stripe library not available", provider="stripe")
        except Exception as e:
            logger.error(f"Error processing Stripe webhook: {e}")
            raise ProviderError(f"Webhook processing error: {e}", provider="stripe")

    def refund_payment(self, transaction_id: str, amount: float | None = None, idempotency_key: str | None = None) -> Any:
        transaction = self.storage.get_transaction(transaction_id)
        if not transaction:
            logger.warning("Stripe transaction not found for refund: " + transaction_id)
            raise ProviderError("Transaction " + transaction_id + " not found", provider="stripe")
        if transaction.status != "completed":
            logger.warning("Cannot refund incomplete transaction: " + transaction_id)
            raise ProviderError(
                "Cannot refund incomplete transaction " + transaction_id,
                provider="stripe",
            )

        # Validate refund amount
        if amount is not None:
            if amount <= 0:
                raise ValidationError("Refund amount must be positive", field="amount", value=amount)
            if amount > transaction.amount:
                raise ValidationError(
                    f"Refund amount ({amount}) cannot exceed original payment amount ({transaction.amount})",
                    field="amount",
                    value=amount,
                )
        try:
            if not self._stripe_available:
                if self._is_dev_mode():
                    # Prevent duplicate mock refunds for the same transaction within 10 seconds
                    # Check for exact matches in refund amount and transaction details for better reliability
                    now = datetime.now(timezone.utc)
                    recent_transactions = getattr(self.storage, "get_transactions_by_user_id", lambda x: [])(transaction.user_id)
                    for tx in recent_transactions:
                        if (
                            tx.metadata.get("mock_transaction")
                            and tx.status == "refunded"
                            and (now - tx.created_at).total_seconds() < 10
                            and tx.metadata.get("refund_amount") == (amount if amount is not None else transaction.amount)
                        ):
                            logger.warning(
                                f"Duplicate mock refund detected for user {transaction.user_id} with same refund amount"
                            )
                            return {
                                "refund_id": tx.metadata.get("stripe_refund_id", f"mock_refund_{uuid.uuid4().hex[:8]}"),
                                "status": "succeeded",
                                "amount": tx.metadata.get("refund_amount", amount if amount is not None else transaction.amount),
                            }
                    logger.info(f"Mock refund Stripe payment: {transaction_id}")
                    refund_amount = amount if amount is not None else transaction.amount
                    refund_id = f"mock_refund_{uuid.uuid4().hex[:8]}"
                    transaction.status = "refunded"
                    transaction.metadata["stripe_refund_id"] = refund_id
                    transaction.metadata["refund_amount"] = refund_amount
                    transaction.metadata["mock_transaction"] = True
                    try:
                        self.storage.save_transaction(transaction)
                    except Exception as storage_error:
                        logger.error(f"Failed to save mock refund transaction to storage: {storage_error}")
                        # Continue with cached transaction for consistency
                    return {
                        "refund_id": refund_id,
                        "status": "succeeded",
                        "amount": refund_amount,
                    }
            import stripe

            stripe.api_key = self.api_key  # type: ignore[attr-defined]
            payment_intent_id = transaction.metadata.get("stripe_payment_intent_id")
            if not payment_intent_id:
                logger.warning("No Stripe PaymentIntent ID in transaction metadata: " + transaction_id)
                raise ProviderError(
                    "No Stripe PaymentIntent ID in transaction metadata",
                    provider="stripe",
                )
            refund_params = {"payment_intent": payment_intent_id}
            if amount is not None:
                refund_params["amount"] = int(amount * 100)
            idempotency_key = idempotency_key or str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{transaction_id}-{amount}"))
            refund = getattr(stripe, "Refund").create(
                **refund_params,
                idempotency_key=idempotency_key,
            )
            transaction.status = "refunded"
            transaction.metadata["stripe_refund_id"] = refund.id
            transaction.metadata["refund_amount"] = amount if amount is not None else transaction.amount
            with self.transactions_lock:
                # Use the original transaction ID as cache key to maintain consistency
                # If there's a collision, update the existing entry instead of creating a new one
                self.transactions[transaction.id] = transaction
            self.storage.update_transaction(transaction)
            logger.info(
                "Stripe refund succeeded: "
                + refund.id
                + " for transaction "
                + transaction.id
                + ", amount: "
                + str(amount if amount is not None else transaction.amount)
                + " "
                + transaction.currency
            )
            return {
                "refund_id": refund.id,
                "status": refund.status,
                "amount": refund.amount / 100.0,
            }
        except ImportError:
            logger.warning("Stripe library not installed. Falling back to mock mode.")
            return super().refund_payment(transaction_id, amount)
        except Exception as e:
            logger.error("Error processing Stripe refund: " + str(e))
            raise ProviderError("Stripe refund error: " + str(e), provider="stripe")

    def get_payment_status(self, transaction_id: str) -> str:
        transaction = self.storage.get_transaction(transaction_id)
        if not transaction:
            logger.warning("Stripe transaction not found for status: " + transaction_id)
            raise ProviderError("Transaction " + transaction_id + " not found", provider="stripe")
        try:
            if not self._stripe_available:
                if self._is_dev_mode():
                    logger.info(f"Mock get Stripe payment status: {transaction_id}")
                    return "completed"
                else:
                    raise ProviderError("stripe library not available. Cannot get Stripe payment status.", provider="stripe")
            import stripe

            stripe.api_key = self.api_key  # type: ignore[attr-defined]
            payment_intent_id = transaction.metadata.get("stripe_payment_intent_id")
            if not payment_intent_id:
                logger.warning("No Stripe PaymentIntent ID in transaction metadata: " + transaction_id)
                raise ProviderError(
                    "No Stripe PaymentIntent ID in transaction metadata",
                    provider="stripe",
                )
            payment_intent = getattr(stripe, "PaymentIntent").retrieve(payment_intent_id)
            logger.debug("Stripe payment status for " + transaction_id + ": " + payment_intent.status)
            # Map Stripe status to our internal status
            status_mapping = {
                "succeeded": "completed",
                "processing": "pending",
                "requires_payment_method": "pending",
                "requires_confirmation": "pending",
                "requires_action": "pending",
                "canceled": "cancelled",
                "failed": "failed",
            }
            mapped_status = status_mapping.get(payment_intent.status, "pending")
            transaction.status = mapped_status
            # Update transaction in cache and storage without changing ID
            with self.transactions_lock:
                self.transactions[transaction.id] = transaction
            self.storage.save_transaction(transaction)
            return mapped_status
        except ImportError:
            logger.warning("Stripe library not installed. Falling back to mock mode.")
            return super().get_payment_status(transaction_id)
        except Exception as e:
            logger.error("Error getting Stripe payment status: " + str(e))
            raise ProviderError("Stripe payment status error: " + str(e), provider="stripe")

    def health_check(self) -> bool:
        """
        Perform a comprehensive health check for the Stripe provider.

        Returns:
            bool: True if the health check passes, False otherwise
        """
        try:
            # In dev mode, if Stripe library is not available, return True for mock behavior
            if not self._stripe_available and self._is_dev_mode():
                logger.info(
                    "Stripe health check: dev mode enabled, Stripe library not available - returning True for mock behavior"
                )
                return True

            # If not in dev mode and Stripe library is not available, fail the health check
            if not self._stripe_available:
                logger.error("Stripe health check failed: stripe library not available and not in dev mode")
                return False

            # In dev mode, if Stripe library is available but API calls fail, return True for mock behavior
            if self._is_dev_mode():
                try:
                    self._perform_health_check()
                    return True
                except Exception as e:
                    logger.info(
                        f"Stripe health check: dev mode enabled, API calls failed - returning True for mock behavior. Error: {e}"
                    )
                    return True

            # Perform actual health check for production mode
            self._perform_health_check()
            return True
        except Exception as e:
            logger.error(f"Stripe health check failed: {e}")
            return False

    def create_checkout_session(
        self,
        user_id: str,
        plan: "PaymentPlan",
        success_url: str,
        cancel_url: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """
        Create a Stripe Checkout Session for the user.

        This method creates a hosted checkout session that redirects users to Stripe's
        payment page. The user will be redirected to success_url or cancel_url after
        completing or canceling the payment.

        Args:
            user_id: The user's unique identifier
            plan: The payment plan to subscribe to
            success_url: URL to redirect to after successful payment
            cancel_url: URL to redirect to after canceled payment
            metadata: Additional metadata to include with the payment

        Returns:
            Dictionary containing:
            - 'url': The checkout session URL that the user should be redirected to
            - 'session_id': The Stripe session ID for retrieving session details

        Raises:
            PaymentFailed: If the checkout session creation fails
        """
        self._validate_metadata(metadata)
        # Basic URL validation
        if not success_url or not isinstance(success_url, str) or not success_url.startswith(("http://", "https://")):
            raise ValidationError("Invalid success_url", field="success_url", value=success_url)
        if not cancel_url or not isinstance(cancel_url, str) or not cancel_url.startswith(("http://", "https://")):
            raise ValidationError("Invalid cancel_url", field="cancel_url", value=cancel_url)
        try:
            import stripe

            # Create checkout session
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": plan.currency.lower(),
                            "product_data": {
                                "name": plan.name,
                                "description": plan.description or "",
                            },
                            "unit_amount": int(plan.price * 100),  # Convert to cents
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                payment_intent_data={
                    "metadata": {
                        **(metadata or {}),
                        "user_id": user_id,
                        "plan_id": plan.id,
                    }
                },
            )

            if not session.url:
                raise PaymentFailed("Stripe did not return a checkout session URL")

            # Create pending transaction for better traceability during beta testing
            transaction_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            transaction = PaymentTransaction(
                id=transaction_id,
                user_id=user_id,
                amount=plan.price,
                currency=plan.currency,
                payment_method="stripe_checkout",
                status="pending",
                created_at=now,
                completed_at=None,
                metadata={
                    **(metadata or {}),
                    "stripe_checkout_session_id": session.id,
                    "plan_id": plan.id,
                    "checkout_session_created": True,
                },
            )

            # Save to storage for persistence
            try:
                self.storage.save_transaction(transaction)
                logger.info(f"Created pending transaction {transaction_id} for checkout session {session.id}")
            except Exception as storage_error:
                logger.error(f"Failed to save pending transaction to storage: {storage_error}")
                # Add to cache for consistency
                with self.transactions_lock:
                    while transaction_id in self.transactions:
                        transaction_id = str(uuid.uuid4())
                        transaction.id = transaction_id
                    self.transactions[transaction_id] = transaction

            logger.info(
                f"Created Stripe checkout session: {session.id} for user {user_id}, "
                f"plan: {plan.id}, amount: {plan.price} {plan.currency}"
            )
            return {
                "url": session.url,
                "session_id": session.id,
            }

        except ImportError:
            logger.warning("stripe library not installed. Falling back to mock mode.")
            # Create mock pending transaction for consistency
            transaction_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            mock_transaction = PaymentTransaction(
                id=transaction_id,
                user_id=user_id,
                amount=plan.price,
                currency=plan.currency,
                payment_method="stripe_checkout",
                status="pending",
                created_at=now,
                completed_at=None,
                metadata={
                    **(metadata or {}),
                    "stripe_checkout_session_id": "mock_session_id",
                    "plan_id": plan.id,
                    "checkout_session_created": True,
                    "mock_transaction": True,
                },
            )

            try:
                self.storage.save_transaction(mock_transaction)
                logger.info(f"Created mock pending transaction {transaction_id} for mock checkout session")
            except Exception as storage_error:
                logger.error(f"Failed to save mock pending transaction to storage: {storage_error}")
                # Continue with cached transaction for consistency

            # Update cache for consistency
            with self.transactions_lock:
                while transaction_id in self.transactions:
                    transaction_id = str(uuid.uuid4())
                self.transactions[transaction_id] = mock_transaction

            return {
                "url": "https://mock-stripe-checkout.com/session/mock_session_id",
                "session_id": "mock_session_id",
            }

    def create_stablecoin_checkout_session(
        self,
        user_id: str,
        amount: float,
        currency: str = "USD",
        stablecoin: str = "usdc",
        success_url: str = "https://example.com/success",
        cancel_url: str = "https://example.com/cancel",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Create a Stripe Checkout Session for stablecoin payments.

        This method creates a hosted checkout session that supports crypto payments.
        According to Stripe docs, crypto payments are handled through Checkout Sessions.

        Args:
            user_id: The user's unique identifier
            amount: Payment amount in the specified currency
            currency: The currency for the payment (USD, EUR, etc.)
            stablecoin: The stablecoin to accept (usdc, usdt, etc.)
            success_url: URL to redirect to after successful payment
            cancel_url: URL to redirect to after canceled payment
            metadata: Additional metadata to include with the payment

        Returns:
            The checkout session URL that the user should be redirected to

        Raises:
            PaymentFailed: If the checkout session creation fails
        """
        self._validate_metadata(metadata)
        # Basic URL validation
        if not success_url or not isinstance(success_url, str) or not success_url.startswith(("http://", "https://")):
            raise ValidationError("Invalid success_url", field="success_url", value=success_url)
        if not cancel_url or not isinstance(cancel_url, str) or not cancel_url.startswith(("http://", "https://")):
            raise ValidationError("Invalid cancel_url", field="cancel_url", value=cancel_url)
        # Validate inputs before attempting Stripe operations
        supported_stablecoins = self.get_supported_stablecoins()
        if stablecoin.lower() not in supported_stablecoins:
            raise ValidationError(f"Unsupported stablecoin: {stablecoin}")

        if not currency or not isinstance(currency, str):
            raise ValidationError("Invalid currency", field="currency", value=currency)

        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValidationError("Amount must be positive", field="amount", value=amount)

        try:
            import stripe

            # Create checkout session for stablecoin payments
            # Note: Crypto payments need to be enabled in Stripe Dashboard
            try:
                session = stripe.checkout.Session.create(
                    payment_method_types=["crypto"],  # Use crypto for stablecoin payments
                    line_items=[
                        {
                            "price_data": {
                                "currency": currency.lower(),
                                "product_data": {
                                    "name": f"Payment ({stablecoin.upper()})",
                                    "description": f"Payment of {amount} {currency} via {stablecoin.upper()}",
                                },
                                "unit_amount": int(amount * 100),
                            },
                            "quantity": 1,
                        }
                    ],
                    mode="payment",
                    success_url=success_url,
                    cancel_url=cancel_url,
                    metadata={
                        **(metadata or {}),
                        "user_id": user_id,
                        "stablecoin": stablecoin,
                        "payment_type": "stablecoin",
                    },
                )
            except stripe.InvalidRequestError as e:
                if "crypto" in str(e).lower() or "payment_method_types" in str(e).lower():
                    logger.warning(f"Crypto payments not enabled in Stripe account, falling back to card payments: {e}")
                    # Fallback to card payments if crypto is not enabled
                    session = stripe.checkout.Session.create(
                        payment_method_types=["card"],
                        line_items=[
                            {
                                "price_data": {
                                    "currency": currency.lower(),
                                    "product_data": {
                                        "name": f"Payment ({stablecoin.upper()})",
                                        "description": f"Payment of {amount} {currency} via {stablecoin.upper()} (card fallback)",
                                    },
                                    "unit_amount": int(amount * 100),
                                },
                                "quantity": 1,
                            }
                        ],
                        mode="payment",
                        success_url=success_url,
                        cancel_url=cancel_url,
                        metadata={
                            **(metadata or {}),
                            "user_id": user_id,
                            "stablecoin": stablecoin,
                            "payment_type": "stablecoin",
                            "fallback_to_card": "true",
                        },
                    )
                else:
                    raise

            logger.info(
                f"Created Stripe stablecoin checkout session: {session.id} for user {user_id}, "
                f"amount: {amount} {currency}, stablecoin: {stablecoin}"
            )

            if not session.url:
                raise PaymentFailed("Stripe did not return a checkout session URL")

            # Create a transaction record for the stablecoin checkout session
            transaction_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)

            # Determine payment method based on whether fallback occurred
            session_metadata = getattr(session, "metadata", {}) or {}
            payment_method = (
                "stripe_card_fallback"
                if session_metadata.get("fallback_to_card") == "true"
                else f"stripe_stablecoin_{stablecoin}"
            )

            # Safely get payment_intent_id (may not be available immediately)
            payment_intent_id = getattr(session, "payment_intent", None)

            transaction = PaymentTransaction(
                id=transaction_id,
                user_id=user_id,
                amount=amount,
                currency=currency,
                payment_method=payment_method,
                status="pending",
                created_at=now,
                completed_at=None,
                metadata={
                    **(metadata or {}),
                    "stripe_checkout_session_id": session.id,
                    "stablecoin": stablecoin,
                    "payment_type": "stablecoin",
                },
            )

            # Only add payment_intent_id if available
            if payment_intent_id:
                transaction.metadata["stripe_payment_intent_id"] = payment_intent_id
            self.storage.save_transaction(transaction)
            with self.transactions_lock:
                while transaction_id in self.transactions:
                    transaction_id = str(uuid.uuid4())
                self.transactions[transaction_id] = transaction

            return session.url

        except ImportError:
            logger.warning("stripe library not installed. Falling back to mock mode.")
            # Create a mock transaction record for the stablecoin checkout session
            transaction_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            mock_transaction = PaymentTransaction(
                id=transaction_id,
                user_id=user_id,
                amount=amount,
                currency=currency,
                payment_method=f"stripe_stablecoin_mock",
                status="pending",
                created_at=now,
                completed_at=None,
                metadata={
                    **(metadata or {}),
                    "stripe_checkout_session_id": "mock_session_id",
                    "stripe_payment_intent_id": "mock_pi_intent",
                    "stablecoin": stablecoin,
                    "payment_type": "stablecoin",
                    "mock_transaction": True,
                },
            )
            try:
                self.storage.save_transaction(mock_transaction)
            except Exception as storage_error:
                logger.error(f"Failed to save mock stablecoin transaction to storage: {storage_error}")
                # Continue with cached transaction for consistency

            with self.transactions_lock:
                while transaction_id in self.transactions:
                    transaction_id = str(uuid.uuid4())
                self.transactions[transaction_id] = mock_transaction

            return "https://mock-stripe-checkout.com/stablecoin/mock_session_id"
        except Exception as e:
            logger.error(f"Error creating stablecoin checkout session: {e}")
            raise PaymentFailed(f"Stablecoin checkout session creation failed: {e}")

    def create_stablecoin_payment_intent(
        self,
        user_id: str,
        amount: float,
        currency: str = "USD",
        stablecoin: str = "usdc",
        metadata: dict[str, Any] | None = None,
    ) -> dict:
        """
        Create a Stripe stablecoin payment intent for crypto payments.

        This method creates a payment intent that can be paid with stablecoins like USDC.
        The payment intent can be used with Stripe's crypto payment flow.

        Args:
            user_id: The user's unique identifier
            amount: Payment amount in the specified currency
            currency: The currency for the payment (USD, EUR, etc.)
            stablecoin: The stablecoin to accept (usdc, usdt, etc.)
            metadata: Additional metadata to include with the payment

        Returns:
            Dictionary containing payment intent details including client_secret

        Raises:
            PaymentFailed: If the payment intent creation fails
        """
        self._validate_metadata(metadata)
        # Validate inputs before attempting Stripe operations
        supported_stablecoins = self.get_supported_stablecoins()
        if stablecoin.lower() not in supported_stablecoins:
            raise ValidationError(f"Unsupported stablecoin: {stablecoin}")

        if not currency or not isinstance(currency, str):
            raise ValidationError("Invalid currency", field="currency", value=currency)

        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValidationError("Amount must be positive", field="amount", value=amount)

        try:
            import stripe

            # Create payment intent for stablecoin payments
            # Note: Crypto payments are handled through Checkout Sessions, not direct PaymentIntents
            payment_intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency.lower(),
                description=f"Stablecoin payment for user {user_id} ({stablecoin.upper()})",
                metadata={
                    **(metadata or {}),
                    "user_id": user_id,
                    "stablecoin": stablecoin,
                    "payment_type": "stablecoin",
                },
                # Enable automatic payment methods for better UX
                automatic_payment_methods={
                    "enabled": True,
                },
            )

            logger.info(
                f"Created Stripe stablecoin payment intent: {payment_intent.id} for user {user_id}, "
                f"amount: {amount} {currency}, stablecoin: {stablecoin}"
            )

            return {
                "id": payment_intent.id,
                "client_secret": payment_intent.client_secret,
                "amount": amount,
                "currency": currency,
                "stablecoin": stablecoin,
                "status": payment_intent.status,
                "metadata": payment_intent.metadata,
            }

        except ImportError:
            logger.warning("stripe library not installed. Falling back to mock mode.")
            return {
                "id": f"mock_stablecoin_intent_{uuid.uuid4().hex[:8]}",
                "client_secret": "mock_client_secret",
                "amount": amount,
                "currency": currency,
                "stablecoin": stablecoin,
                "status": "requires_payment_method",
                "metadata": metadata or {},
            }
        except Exception as e:
            logger.error(f"Unexpected error creating stablecoin payment intent: {e}")
            raise PaymentFailed(f"Payment intent creation failed: {e}")

    def process_stablecoin_payment(
        self,
        user_id: str,
        amount: float,
        currency: str = "USD",
        stablecoin: str = "usdc",
        metadata: dict[str, Any] | None = None,
    ) -> PaymentTransaction:
        """
        Process a stablecoin payment using Stripe's crypto payment flow.
        """
        if not user_id or not isinstance(user_id, str):
            raise ValidationError("Invalid user_id", field="user_id", value=user_id)
        self._validate_metadata(metadata)
        # Validate currency against supported currencies
        supported_currencies = self._get_capabilities().supported_currencies
        if currency.upper() not in supported_currencies:
            raise ValidationError(f"Unsupported currency: {currency}", field="currency", value=currency)
        # Validate amount against min/max
        capabilities = self._get_capabilities()
        if amount < capabilities.min_amount or amount > capabilities.max_amount:
            raise ValidationError(
                f"Amount must be between {capabilities.min_amount} and {capabilities.max_amount}", field="amount", value=amount
            )
        supported_stablecoins = self.get_supported_stablecoins()
        if stablecoin.lower() not in supported_stablecoins:
            raise ValidationError(f"Unsupported stablecoin: {stablecoin}")
        try:
            # Check if Stripe library is available
            if not self._stripe_available:
                # Only create mock transactions in development/testing environments
                if self._is_dev_mode():
                    # Prevent duplicate mock stablecoin transactions for the same user within 10 seconds
                    # Check for exact matches in amount, currency, user_id, and stablecoin for better reliability
                    now = datetime.now(timezone.utc)
                    recent_transactions = getattr(self.storage, "get_transactions_by_user_id", lambda x: [])(user_id)
                    for tx in recent_transactions:
                        if (
                            tx.metadata.get("mock_transaction")
                            and (now - tx.created_at).total_seconds() < 10
                            and tx.amount == amount
                            and tx.currency == currency
                            and tx.metadata.get("stablecoin") == stablecoin
                        ):
                            logger.warning(
                                f"Duplicate mock stablecoin transaction detected for user {user_id} with same amount, currency, and stablecoin"
                            )
                            return tx
                    # Generate unique transaction ID with storage check to prevent duplicates
                    transaction_id = self._generate_unique_transaction_id()
                    transaction = PaymentTransaction(
                        id=transaction_id,
                        user_id=user_id,
                        amount=amount,
                        currency=currency,
                        payment_method=f"stripe_stablecoin_{stablecoin}",
                        status="completed",
                        created_at=now,
                        completed_at=now,
                        metadata={
                            **(metadata or {}),
                            "stripe_payment_intent_id": f"mock_pi_{uuid.uuid4().hex[:8]}",
                            "client_secret": "mock_client_secret",
                            "stablecoin": stablecoin,
                            "payment_type": "stablecoin",
                            "mock_transaction": True,
                        },
                    )
                    with self.transactions_lock:
                        self.transactions[transaction_id] = transaction
                    try:
                        self.storage.save_transaction(transaction)
                        logger.info(
                            f"Mock stablecoin payment processed: {transaction_id} for user {user_id}, amount: {amount} {currency}"
                        )
                    except Exception as storage_error:
                        logger.error(f"Failed to save mock stablecoin transaction to storage: {storage_error}")
                        # Continue with cached transaction for consistency
                    return transaction
                else:
                    # In production, fail fast if Stripe library is not available
                    raise ProviderError(
                        "stripe library not available. Cannot process stablecoin payments in production.", provider="stripe"
                    )

            # Create the payment intent
            payment_intent_data = self.create_stablecoin_payment_intent(
                user_id=user_id,
                amount=amount,
                currency=currency,
                stablecoin=stablecoin,
                metadata=metadata,
            )

            # Create transaction record with unique ID generation
            transaction_id = self._generate_unique_transaction_id()
            now = datetime.now(timezone.utc)

            transaction = PaymentTransaction(
                id=transaction_id,
                user_id=user_id,
                amount=amount,
                currency=currency,
                payment_method=f"stripe_stablecoin_{stablecoin}",
                status="pending",
                created_at=now,
                completed_at=None,
                metadata={
                    **(metadata or {}),
                    "stripe_payment_intent_id": payment_intent_data["id"],
                    "client_secret": payment_intent_data["client_secret"],
                    "stablecoin": stablecoin,
                    "payment_type": "stablecoin",
                },
            )

            # Save transaction to storage and update cache atomically
            with self.transactions_lock:
                self.transactions[transaction_id] = transaction
                try:
                    self.storage.save_transaction(transaction)
                except Exception as storage_error:
                    logger.error(f"Failed to save stablecoin transaction to storage: {storage_error}")
                    # For production environments, log critical storage failure but don't fail payment
                    if not self._is_dev_mode():
                        logger.critical(
                            f"CRITICAL: Stablecoin payment succeeded but storage failed for transaction {transaction_id}. Payment amount: {amount} {currency}"
                        )
                        # Add storage failure flag to transaction metadata
                        transaction.metadata["storage_failed"] = True
                        transaction.metadata["storage_error"] = str(storage_error)
                    # For mock/dev environments, continue with cached transaction
                    else:
                        logger.warning("Continuing with cached transaction due to storage failure (mock/dev mode)")

            logger.info(
                f"Created stablecoin payment transaction: {transaction_id} for user {user_id}, "
                f"amount: {amount} {currency}, stablecoin: {stablecoin}"
            )

            # Return the transaction we just saved (avoid race condition with get_transaction)
            return transaction

        except Exception as e:
            logger.error(f"Error processing stablecoin payment: {e}")
            raise PaymentFailed(f"Stablecoin payment processing error: {e}")

    def verify_stablecoin_payment(self, transaction_id: str) -> bool:
        """
        Verify a stablecoin payment by checking the Stripe payment intent status.

        Args:
            transaction_id: The transaction ID to verify

        Returns:
            True if payment is confirmed, False otherwise

        Raises:
            ProviderError: If verification fails
        """
        try:
            import stripe

            # Get transaction from storage
            transaction = self.storage.get_transaction(transaction_id)

            if not transaction:
                logger.warning(f"Stablecoin transaction not found: {transaction_id}")
                return False

            payment_intent_id = transaction.metadata.get("stripe_payment_intent_id")
            if not payment_intent_id:
                logger.warning(f"No payment intent ID in transaction metadata: {transaction_id}")
                return False

            # Retrieve payment intent from Stripe
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            if payment_intent.status == "succeeded":
                logger.info(f"Stablecoin payment confirmed: {transaction_id}")
                # Update transaction status to completed
                transaction.status = "completed"
                transaction.completed_at = datetime.now(timezone.utc)
                # Update transaction in cache and storage without changing ID
                with self.transactions_lock:
                    self.transactions[transaction.id] = transaction
                self.storage.save_transaction(transaction)
                return True
            elif payment_intent.status in ["requires_payment_method", "requires_confirmation", "requires_action"]:
                logger.info(f"Stablecoin payment pending: {transaction_id}, status: {payment_intent.status}")
                return False
            else:
                logger.warning(f"Stablecoin payment failed: {transaction_id}, status: {payment_intent.status}")
                # Update transaction status to failed
                transaction.status = "failed"
                # Update transaction in cache and storage without changing ID
                with self.transactions_lock:
                    self.transactions[transaction.id] = transaction
                self.storage.save_transaction(transaction)
                return False

        except ImportError:
            logger.warning("stripe library not installed. Cannot verify stablecoin payment.")
            return False
        except Exception as e:
            logger.error(f"Error verifying stablecoin payment: {e}")
            raise ProviderError(f"Stablecoin payment verification error: {e}", provider="stripe")

    def create_customer(
        self,
        user_id: str,
        email: str,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict:
        """
        Create a Stripe customer for subscription management.

        Args:
            user_id: The user's unique identifier
            email: Customer's email address
            name: Customer's name (optional)
            metadata: Additional metadata

        Returns:
            Dictionary containing customer details

        Raises:
            PaymentFailed: If customer creation fails
        """
        self._validate_metadata(metadata)
        try:
            import stripe

            customer_data = {
                "email": email,
                "metadata": {
                    **(metadata or {}),
                    "user_id": user_id,
                },
            }
            if name:
                customer_data["name"] = name

            customer = stripe.Customer.create(**customer_data)

            logger.info(f"Created Stripe customer: {customer.id} for user {user_id}")

            return {
                "id": customer.id,
                "email": customer.email,
                "name": customer.name,
                "metadata": customer.metadata,
            }

        except ImportError:
            logger.warning("stripe library not installed. Falling back to mock mode.")
            return {
                "id": f"mock_customer_{uuid.uuid4().hex[:8]}",
                "email": email,
                "name": name,
                "metadata": metadata or {},
            }
        except Exception as e:
            logger.error(f"Error creating Stripe customer: {e}")
            raise PaymentFailed(f"Customer creation failed: {e}")

    def create_customer_portal_session(
        self,
        customer_id: str,
        return_url: str,
    ) -> str:
        """
        Create a customer portal session for subscription management.

        Args:
            customer_id: The Stripe customer ID
            return_url: URL to return to after portal session

        Returns:
            The customer portal session URL

        Raises:
            PaymentFailed: If portal session creation fails
        """
        try:
            import stripe

            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )

            logger.info(f"Created customer portal session for customer: {customer_id}")

            if not session.url:
                raise PaymentFailed("Stripe did not return a customer portal session URL")

            return session.url

        except ImportError:
            logger.warning("stripe library not installed. Falling back to mock mode.")
            return "https://mock-stripe-portal.com/session/mock_portal_id"
        except Exception as e:
            logger.error(f"Error creating customer portal session: {e}")
            raise PaymentFailed(f"Customer portal session creation failed: {e}")

    def get_supported_stablecoins(self) -> list[str]:
        """
        Get list of supported stablecoins for payments.

        Returns:
            List of supported stablecoin codes
        """
        # Based on Stripe's current stablecoin support (WARNING: this list may change, check Stripe docs):
        # - USDC on Ethereum, Solana, Polygon, and Base
        # - USDP on Ethereum and Solana
        # - USDG on Ethereum
        # TODO: Consider making this configurable or fetching from Stripe API for production use
        # Current hardcoded list is sufficient for beta release but should be reviewed for production
        #
        # Beta Release Notes:
        # - This list covers the most commonly used stablecoins supported by Stripe
        # - If users attempt unsupported stablecoins, they will receive a ValidationError
        # - For production, consider implementing dynamic stablecoin support via Stripe API
        # - Monitor Stripe documentation for new stablecoin additions
        return ["usdc", "usdp", "usdg"]
