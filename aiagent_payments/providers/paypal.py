"""
PayPal payment provider for the AI Agent Payments SDK.
"""

import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests

from aiagent_payments.storage import MemoryStorage, StorageBackend

from ..exceptions import ConfigurationError, PaymentFailed, ProviderError, ValidationError
from ..models import PaymentTransaction
from ..utils import retry
from .base import PaymentProvider

try:
    from ratelimit import limits, sleep_and_retry

    RATE_LIMIT_AVAILABLE = True
except ImportError:
    RATE_LIMIT_AVAILABLE = False

    # Fallback decorators that do nothing
    def limits(calls, period):
        def decorator(func):
            return func

        return decorator

    def sleep_and_retry(func):
        return func


logger = logging.getLogger(__name__)


class PayPalProvider(PaymentProvider):
    """
    PayPal payment provider.

    Note: The in-memory transactions cache (self.transactions) stores only PaymentTransaction objects
    from capture_order, process_payment, refund_payment, verify_payment, and get_payment_status.
    Order creation data is stored in self.storage but not cached in self.transactions to avoid
    confusion and maintain clear separation of concerns.
    """

    # Add centralized status mapping
    STATUS_MAPPING = {
        "completed": "completed",
        "approved": "completed",
        "captured": "completed",
        "pending": "pending",
        "declined": "failed",
        "expired": "failed",
        "voided": "cancelled",
        "cancelled": "cancelled",
    }

    # Rate limiting configuration (100 calls per 60 seconds - adjust based on PayPal's limits)
    RATE_LIMIT_CALLS = 100
    RATE_LIMIT_PERIOD = 60

    # TODO: Add support for PayPal subscription and recurring payments
    # TODO: Add support for PayPal payout APIs
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        sandbox: bool = True,
        storage: StorageBackend | None = None,
        webhook_id: str | None = None,
        return_url: str | None = None,
        cancel_url: str | None = None,
        timeout: int = 30,
        mock_mode: bool = False,  # Add explicit mock_mode flag
    ):
        self.mock_mode = mock_mode
        self.client_id = client_id or os.getenv("PAYPAL_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("PAYPAL_CLIENT_SECRET")
        self.sandbox = sandbox
        self.storage = storage or MemoryStorage()
        self.environment = "sandbox" if sandbox else "live"
        # Validate and set timeout (recommended: 5–10 seconds)
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ConfigurationError("Timeout must be a positive number.")
        self.timeout = timeout or 10  # Default to 10 seconds
        self.transactions: dict[str, PaymentTransaction] = {}  # In-memory transaction cache
        self.transactions_lock = threading.Lock()  # Thread-safe lock for cache updates

        # Handle requests library availability
        try:
            import requests

            self.session = requests.Session()
            self._requests_available = True
        except ImportError:
            raise ConfigurationError("The 'requests' library is required for PayPalProvider.")

        self.webhook_id = webhook_id or os.getenv("PAYPAL_WEBHOOK_ID")
        self.return_url = return_url or os.getenv("PAYPAL_RETURN_URL")
        self.cancel_url = cancel_url or os.getenv("PAYPAL_CANCEL_URL")

        # Validate URLs and enforce production requirements
        self._validate_urls()

        # Require webhook_id in production mode
        if not self.sandbox and not self.webhook_id:
            raise ConfigurationError("webhook_id must be provided in production mode.")

        # Require return_url and cancel_url in production mode
        if not self.sandbox and (not self.return_url or not self.cancel_url):
            raise ConfigurationError("return_url and cancel_url must be provided in production mode.")

        super().__init__("PayPalProvider")

        # Only require credentials if not in mock mode
        if (self.client_id is None or self.client_secret is None) and not self.mock_mode:
            raise ProviderError(
                "PayPal client_id and client_secret must be set via argument or PAYPAL_CLIENT_ID/PAYPAL_CLIENT_SECRET env vars."
            )

        if self.client_id:
            self.client_id = str(self.client_id)
        if self.client_secret:
            self.client_secret = str(self.client_secret)

        logger.info(f"PayPalProvider initialized for {self.environment} environment")

    def _validate_urls(self):
        """Validate return and cancel URLs."""
        for url_name, url in [("return_url", self.return_url), ("cancel_url", self.cancel_url)]:
            if not url:
                raise ValidationError(f"{url_name} cannot be empty", field=url_name, value=url)

            try:
                parsed = urlparse(url)
                if not parsed.scheme or not parsed.netloc:
                    raise ValidationError(f"{url_name} must be a valid URL", field=url_name, value=url)
                if parsed.scheme not in ["http", "https"]:
                    raise ValidationError(f"{url_name} must use HTTP or HTTPS", field=url_name, value=url)
                # PayPal requires HTTPS for production
                if not self.sandbox and parsed.scheme != "https":
                    raise ValidationError(f"{url_name} must use HTTPS for production", field=url_name, value=url)
            except Exception as e:
                raise ValidationError(f"Invalid {url_name}: {e}", field=url_name, value=url)

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
        if self._requests_available:
            if not self.client_id or not isinstance(self.client_id, str):
                raise ConfigurationError("PayPal client_id is required for PayPalProvider.")
            if not self.client_secret or not isinstance(self.client_secret, str):
                raise ConfigurationError("PayPal client_secret is required for PayPalProvider.")

    def _perform_health_check(self):
        """
        Perform a health check for the PayPal provider.
        Raises:
            Exception: If the health check fails
        """
        try:
            # Try to obtain an access token as a health check
            token = self._get_access_token()
            if not token:
                raise Exception("PayPal access token could not be retrieved.")
        except Exception as e:
            raise Exception(f"PayPal health check failed: {e}")

    @property
    def api_base(self) -> str:
        """Return the base URL for the PayPal API (sandbox or live)."""
        return "https://api-m.sandbox.paypal.com" if self.sandbox else "https://api-m.paypal.com"

    def _get_session(self):
        """Get the requests session, raising ImportError if not available."""
        if not self._requests_available:
            raise ImportError("requests library not available")
        if self.session is None:
            raise ImportError("requests library not available")
        return self.session

    @sleep_and_retry
    @limits(calls=RATE_LIMIT_CALLS, period=RATE_LIMIT_PERIOD)
    def _rate_limited_request(self, method: str, url: str, **kwargs):
        """Make a rate-limited HTTP request to PayPal API."""
        session = self._get_session()
        if method.upper() == "GET":
            return session.get(url, **kwargs)
        elif method.upper() == "POST":
            return session.post(url, **kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

    def _validate_currency(self, currency: str) -> None:
        """Validate currency against supported currencies."""
        capabilities = self._get_capabilities()
        if currency.upper() not in capabilities.supported_currencies:
            raise ValidationError(
                f"Currency {currency} is not supported. Supported currencies: {capabilities.supported_currencies}",
                field="currency",
                value=currency,
            )

    def _validate_amount(self, amount: float) -> None:
        """Validate amount against min/max limits."""
        capabilities = self._get_capabilities()
        if amount < capabilities.min_amount:
            raise ValidationError(f"Amount {amount} is below minimum {capabilities.min_amount}", field="amount", value=amount)
        if amount > capabilities.max_amount:
            raise ValidationError(f"Amount {amount} exceeds maximum {capabilities.max_amount}", field="amount", value=amount)

    def _get_access_token(self) -> str:
        """Obtain an OAuth2 access token from PayPal."""
        try:
            if not self._requests_available:
                raise ImportError("requests library not available")

            # Type assertion since we validate these in __init__
            client_id = str(self.client_id)
            client_secret = str(self.client_secret)

            # Type assertion since we check _requests_available above
            session = self.session
            assert session is not None  # type: ignore

            resp = self._rate_limited_request(
                "POST",
                f"{self.api_base}/v1/oauth2/token",
                headers={"Accept": "application/json", "Accept-Language": "en_US"},
                data={"grant_type": "client_credentials"},
                auth=(client_id, client_secret),
                timeout=self.timeout,
            )

            # Handle specific HTTP errors
            if hasattr(resp, "status_code") and isinstance(resp.status_code, (int, float)):
                if resp.status_code == 401:
                    raise ProviderError("PayPal authentication failed. Check client_id and client_secret.", provider="paypal")
                elif resp.status_code == 403:
                    raise ProviderError("PayPal access forbidden. Check API permissions.", provider="paypal")
                elif resp.status_code == 429:
                    raise ProviderError("PayPal rate limit exceeded. Please retry later.", provider="paypal")
                elif resp.status_code == 422:
                    raise ProviderError("PayPal request unprocessable. Check request format.", provider="paypal")
                elif resp.status_code >= 500:
                    raise ProviderError(f"PayPal server error: {resp.status_code}", provider="paypal")

            resp.raise_for_status()
            try:
                return resp.json()["access_token"]
            except (ValueError, KeyError, TypeError) as json_error:
                logger.error(
                    f"Failed to parse PayPal response: {json_error}, raw response: {getattr(resp, 'text', 'No response text')}"
                )
                raise ProviderError(f"Failed to obtain PayPal access token: Invalid response format", provider="paypal")
        except requests.exceptions.Timeout:
            logger.error("PayPal API request timed out for access token")
            raise ProviderError("PayPal API request timed out", provider="paypal")
        except ImportError:
            logger.warning("requests library not installed. Cannot obtain access token.")
            raise ImportError("requests library not available")
        except ProviderError:
            # Re-raise provider errors as-is
            raise
        except Exception as e:
            logger.error(f"Error obtaining PayPal access token: {e}")
            raise ProviderError(f"Failed to obtain PayPal access token: {e}", provider="paypal")

    def _create_mock_transaction(
        self, user_id: str, amount: float, currency: str, metadata: dict[str, Any] | None = None
    ) -> PaymentTransaction:
        """Create a mock transaction for testing when requests library is not available or mock_mode is enabled.
        Deduplication uses a hash-based mock_key for reliability in high-concurrency scenarios.
        Thread-safe implementation to prevent duplicate transactions in concurrent test scenarios.
        """
        # Generate unique transaction ID for mock mode
        mock_key = self._generate_unique_transaction_id()

        now = datetime.now(timezone.utc)
        mock_metadata = {
            **(metadata or {}),
            "mock_key": mock_key,
            "paypal_order_id": f"mock_order_{uuid.uuid4().hex[:8]}_{int(now.timestamp() * 1000000)}",
            "paypal_capture_id": f"mock_capture_{uuid.uuid4().hex[:8]}_{int(now.timestamp() * 1000000)}",
            "paypal_environment": self.environment,
            "mock_transaction": True,
            "mock_timestamp": now.isoformat(),
        }
        transaction = PaymentTransaction(
            id=mock_key,  # Use the generated mock_key
            user_id=user_id,
            amount=amount,
            currency=currency,
            payment_method="paypal",
            status="completed",
            created_at=now,
            completed_at=now,
            metadata=mock_metadata,
        )

        # Cache the transaction and save to storage atomically
        with self.transactions_lock:
            self.transactions[mock_key] = transaction
            try:
                self.storage.save_transaction(transaction)
            except Exception as storage_error:
                logger.error(f"Failed to save mock transaction to storage: {storage_error}")
                # Clean up the placeholder if storage fails
                self._cleanup_reserved_placeholder(mock_key)

        return transaction

    def _generate_idempotency_key(self, user_id: str, amount: float, currency: str, timestamp: str | None = None) -> str:
        """Generate a unique idempotency key with timestamp to avoid conflicts."""
        if timestamp is None:
            timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{user_id}-{amount}-{currency}-{timestamp}"))

    @retry(
        exceptions=Exception,
        max_attempts=3,
        logger=logger,
        retry_message="Retrying PayPal payment...",
    )
    def create_order(
        self,
        user_id: str,
        amount: float,
        currency: str = "USD",
        return_url: str | None = None,
        cancel_url: str | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        """
        Create a PayPal order and return the order details including approval link.

        This is the first step in the PayPal Checkout flow. The returned order
        contains an 'approve' link that the user must visit to approve the payment.

        Args:
            user_id: Unique identifier for the user
            amount: Payment amount
            currency: Currency code (default: USD)
            return_url: URL to redirect user after payment approval (defaults to configured URL)
            cancel_url: URL to redirect user if they cancel (defaults to configured URL)
            metadata: Optional additional metadata
            idempotency_key: Optional idempotency key for the request

        Returns:
            dict: PayPal order response containing order ID, status, and approval links

        Raises:
            ValidationError: If parameters are invalid
            PaymentFailed: If order creation fails
        """
        if not user_id or not isinstance(user_id, str):
            raise ValidationError("Invalid user_id", field="user_id", value=user_id)
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValidationError("Amount must be positive", field="amount", value=amount)
        if not currency or not isinstance(currency, str):
            raise ValidationError("Invalid currency", field="currency", value=currency)

        # Validate currency and amount
        self._validate_currency(currency)
        self._validate_amount(amount)

        # Use configured URLs if not provided
        return_url = return_url or self.return_url
        cancel_url = cancel_url or self.cancel_url

        # Validate URLs are provided
        if not return_url or not cancel_url:
            raise ValidationError("return_url and cancel_url must be provided.")

        # Validate provided URLs
        for url_name, url in [("return_url", return_url), ("cancel_url", cancel_url)]:
            if url:
                try:
                    parsed = urlparse(url)
                    if not parsed.scheme or not parsed.netloc:
                        raise ValidationError(f"{url_name} must be a valid URL", field=url_name, value=url)
                    if parsed.scheme not in ["http", "https"]:
                        raise ValidationError(f"{url_name} must use HTTP or HTTPS", field=url_name, value=url)
                    if not self.sandbox and parsed.scheme != "https":
                        raise ValidationError(f"{url_name} must use HTTPS for production", field=url_name, value=url)
                except Exception as e:
                    raise ValidationError(f"Invalid {url_name}: {e}", field=url_name, value=url)

        try:
            access_token = self._get_access_token()
            order_payload = {
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "amount": {
                            "currency_code": currency.upper(),
                            "value": f"{amount:.2f}".rstrip("0").rstrip(".") if amount == int(amount) else f"{amount:.2f}",
                        },
                        "custom_id": user_id,
                        "description": f"Payment for {user_id}",
                    }
                ],
                "application_context": {
                    "return_url": return_url,
                    "cancel_url": cancel_url,
                },
            }

            # Generate unique idempotency key with timestamp
            idempotency_key = idempotency_key or self._generate_idempotency_key(user_id, amount, currency)

            resp = self._rate_limited_request(
                "POST",
                f"{self.api_base}/v2/checkout/orders",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {access_token}",
                    "PayPal-Request-Id": idempotency_key,
                },
                json=order_payload,
                timeout=self.timeout,
            )

            # Handle specific HTTP errors
            if hasattr(resp, "status_code") and isinstance(resp.status_code, (int, float)):
                if resp.status_code == 400:
                    try:
                        error_data = resp.json()
                        error_message = error_data.get("message", "Bad request")
                        error_details = error_data.get("details", [])
                        detailed_message = f"{error_message}: {error_details}" if error_details else error_message
                        raise PaymentFailed(f"PayPal order creation failed: {detailed_message}")
                    except (ValueError, KeyError, TypeError) as json_error:
                        logger.error(
                            f"Failed to parse PayPal response: {json_error}, raw response: {getattr(resp, 'text', 'No response text')}"
                        )
                        raise PaymentFailed(f"PayPal order creation failed: Bad request (invalid response format)")
                elif resp.status_code == 403:
                    raise PaymentFailed("PayPal access forbidden. Check API permissions.")
                elif resp.status_code == 409:
                    raise PaymentFailed("PayPal order with this idempotency key already exists")
                elif resp.status_code == 422:
                    raise PaymentFailed("PayPal request unprocessable. Check request format.")
                elif resp.status_code >= 500:
                    raise PaymentFailed(f"PayPal server error: {resp.status_code}")

            resp.raise_for_status()
            try:
                order_response = resp.json()
            except (ValueError, KeyError, TypeError) as json_error:
                logger.error(
                    f"Failed to parse PayPal response: {json_error}, raw response: {getattr(resp, 'text', 'No response text')}"
                )
                raise PaymentFailed(f"PayPal order creation failed: Invalid response format")

            logger.info(
                f"PayPal order created: {order_response.get('id')} for user {user_id}, "
                f"amount: {amount} {currency}, status: {order_response.get('status')}"
            )

            return order_response

        except PaymentFailed:
            # Re-raise payment failures as-is
            raise
        except requests.exceptions.Timeout:
            logger.error(f"PayPal API request timed out for create_order: {user_id}, {amount}, {currency}")
            raise PaymentFailed("PayPal API request timed out")
        except Exception as e:
            logger.error(f"Error creating PayPal order: {e}")
            raise PaymentFailed(f"PayPal order creation error: {e}")

    @retry(
        exceptions=Exception,
        max_attempts=3,
        logger=logger,
        retry_message="Retrying PayPal order capture...",
    )
    def capture_order(
        self,
        user_id: str,
        order_id: str,
        metadata: dict[str, Any] | None = None,
        amount: float | None = None,
        currency: str = "USD",
    ) -> PaymentTransaction:
        """
        Capture a PayPal order after user approval.

        This is the second step in the PayPal Checkout flow. Call this method
        after the user has approved the payment via the approval link.

        Args:
            user_id: Unique identifier for the user
            order_id: PayPal order ID from the create_order response
            metadata: Optional additional metadata
            amount: Optional amount for fallback scenarios (default: None)
            currency: Currency code for fallback scenarios (default: USD)

        Returns:
            PaymentTransaction: The completed payment transaction

        Raises:
            ValidationError: If parameters are invalid
            PaymentFailed: If order capture fails
        """
        if not user_id or not isinstance(user_id, str):
            raise ValidationError("Invalid user_id", field="user_id", value=user_id)
        if not order_id or not isinstance(order_id, str):
            raise ValidationError("Invalid order_id", field="order_id", value=order_id)

        # Check for duplicate transactions for the same order_id
        if not self.mock_mode:
            recent_transactions = getattr(self.storage, "get_transactions_by_user_id", lambda x: [])(user_id)
            for tx in recent_transactions:
                if tx.metadata.get("paypal_order_id") == order_id and tx.status in ["completed", "pending"]:
                    logger.warning(f"Duplicate capture attempt for order {order_id}")
                    return tx

        try:
            access_token = self._get_access_token()

            resp = self._rate_limited_request(
                "POST",
                f"{self.api_base}/v2/checkout/orders/{order_id}/capture",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {access_token}",
                },
                timeout=self.timeout,
            )

            # Handle specific HTTP errors
            if hasattr(resp, "status_code") and isinstance(resp.status_code, (int, float)):
                if resp.status_code == 400:
                    try:
                        error_data = resp.json()
                        raise PaymentFailed(f"PayPal order capture failed: {error_data.get('message', 'Bad request')}")
                    except (ValueError, KeyError, TypeError) as json_error:
                        logger.error(
                            f"Failed to parse PayPal response: {json_error}, raw response: {getattr(resp, 'text', 'No response text')}"
                        )
                        raise PaymentFailed(f"PayPal order capture failed: Bad request (invalid response format)")
                elif resp.status_code == 403:
                    raise PaymentFailed("PayPal access forbidden. Check API permissions.")
                elif resp.status_code == 404:
                    raise PaymentFailed(f"PayPal order {order_id} not found")
                elif resp.status_code == 422:
                    raise PaymentFailed("PayPal request unprocessable. Check request format.")
                elif resp.status_code >= 500:
                    raise PaymentFailed(f"PayPal server error: {resp.status_code}")

            resp.raise_for_status()
            try:
                response = resp.json()
            except (ValueError, KeyError, TypeError) as json_error:
                logger.error(
                    f"Failed to parse PayPal response: {json_error}, raw response: {getattr(resp, 'text', 'No response text')}"
                )
                raise PaymentFailed(f"PayPal order capture failed: Invalid response format")

            # Validate response structure
            if "id" not in response:
                raise PaymentFailed("Invalid PayPal response: missing order ID")
            if "purchase_units" not in response or not response["purchase_units"]:
                raise PaymentFailed("Invalid PayPal response: missing purchase units")

            purchase_unit = response["purchase_units"][0]
            if "payments" not in purchase_unit or "captures" not in purchase_unit["payments"]:
                raise PaymentFailed("Invalid PayPal response: missing capture data")

            captures = purchase_unit["payments"]["captures"]
            if not captures:
                raise PaymentFailed("Invalid PayPal response: captures array is empty")

            capture_data = captures[0]
            if "amount" not in capture_data:
                raise PaymentFailed("Invalid PayPal response: missing amount data")
            if "id" not in capture_data:
                raise PaymentFailed("Invalid PayPal response: missing capture ID")

            # Validate amount structure
            amount_data = capture_data["amount"]
            if "value" not in amount_data:
                raise PaymentFailed("Invalid PayPal response: missing amount value")
            if "currency_code" not in amount_data:
                raise PaymentFailed("Invalid PayPal response: missing currency code")

            # Validate response status
            if "status" not in response:
                raise PaymentFailed("Invalid PayPal response: missing status")

            # Extract values from response
            order_id = response["id"]
            status = response["status"].lower()
            amount = float(amount_data["value"])
            currency = amount_data["currency_code"]
            now = datetime.now(timezone.utc)

            # Map PayPal status to internal status using centralized mapping
            internal_status = self.STATUS_MAPPING.get(status, "pending")

            # Generate transaction ID and extract capture data
            transaction_id = str(uuid.uuid4())
            capture_data = response.get("purchase_units", [{}])[0].get("payments", {}).get("captures", [{}])[0]
            capture_id = capture_data.get("id", "unknown_capture_id")

            # Create transaction with updated status
            transaction = PaymentTransaction(
                id=transaction_id,
                user_id=user_id,
                amount=amount,
                currency=currency,
                payment_method="paypal",
                status=internal_status,
                created_at=now,
                completed_at=now if internal_status == "completed" else None,
                metadata={
                    **(metadata or {}),
                    "paypal_order_id": order_id,
                    "paypal_capture_id": capture_id,
                    "paypal_environment": self.environment,
                    "paypal_completed_at": capture_data.get("update_time"),
                    "paypal_status": status,  # Store original PayPal status
                },
            )

            # Update cache and save to storage atomically
            with self.transactions_lock:
                if transaction_id in self.transactions:
                    existing_transaction = self.transactions[transaction_id]
                    if existing_transaction.metadata.get("paypal_order_id") == order_id:
                        logger.warning(f"Transaction {transaction_id} already exists for order {order_id}")
                        return existing_transaction
                    if existing_transaction.status != transaction.status:
                        logger.info(
                            f"Updating transaction {transaction_id} status from {existing_transaction.status} to {transaction.status}"
                        )
                self.transactions[transaction_id] = transaction

                try:
                    self.storage.save_transaction(transaction)
                except Exception as storage_error:
                    logger.error(f"Failed to save transaction to storage: {storage_error}")
                    # For production environments, log critical storage failure but don't fail payment
                    if not self.mock_mode and not self._is_dev_mode():
                        logger.critical(
                            f"CRITICAL: Payment succeeded but storage failed for transaction {transaction_id}. Payment amount: {amount} {currency}"
                        )
                        # Add storage failure flag to transaction metadata
                        transaction.metadata["storage_failed"] = True
                        transaction.metadata["storage_error"] = str(storage_error)
                    # For mock/dev environments, continue with cached transaction
                    else:
                        logger.warning("Continuing with cached transaction due to storage failure (mock/dev mode)")

            logger.info(
                f"PayPal payment processed: {transaction.id} for user {user_id}, "
                f"amount: {amount} {currency}, status: {status}"
            )

            # Return the transaction we just saved (avoid race condition with get_transaction)
            return transaction

        except PaymentFailed:
            # Re-raise payment failures as-is
            raise
        except requests.exceptions.Timeout:
            logger.error(f"PayPal API request timed out for capture_order: {user_id}, {order_id}, {amount}, {currency}")
            raise PaymentFailed("PayPal API request timed out")
        except Exception as e:
            logger.error(f"Error capturing PayPal order: {e}")
            raise PaymentFailed(f"PayPal order capture error: {e}")

    @retry(
        exceptions=Exception,
        max_attempts=3,
        logger=logger,
        retry_message="Retrying PayPal payment...",
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
        Process a PayPal payment using the two-step flow.

        WARNING: This method creates an order and immediately attempts to capture it.
        This will only work in development/testing environments or with special PayPal
        approval for reference transactions. For production use, it's recommended to
        use create_order() and capture_order() separately to handle the user approval step properly.

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
        self._validate_currency(currency)
        self._validate_amount(amount)

        # Validate metadata to prevent TypeError in dictionary unpacking
        self._validate_metadata(metadata)

        try:
            # Step 1: Create the order
            order_response = self.create_order(
                user_id=user_id,
                amount=amount,
                currency=currency,
                metadata=metadata,
                idempotency_key=idempotency_key,
            )

            order_id = order_response["id"]
            order_status = order_response.get("status", "CREATED")

            # Check if order was created successfully
            if order_status not in ["CREATED", "SAVED"]:
                raise PaymentFailed(f"PayPal order creation failed with status: {order_status}")

            # Step 2: Capture the order
            # Note: This will only work if the order was pre-approved or if using
            # PayPal's reference transactions (requires special approval)
            transaction = self.capture_order(
                user_id=user_id,
                order_id=order_id,
                metadata=metadata,
                amount=amount,
                currency=currency,
            )

            return transaction

        except PaymentFailed:
            # Re-raise payment failures as-is
            raise
        except requests.exceptions.Timeout:
            logger.error(f"PayPal API request timed out for process_payment: {user_id}, {amount}, {currency}")
            raise PaymentFailed("PayPal API request timed out")
        except Exception as e:
            logger.error(f"Error processing PayPal payment: {e}")
            raise PaymentFailed(f"PayPal payment processing error: {e}")

    @retry(
        exceptions=Exception,
        max_attempts=3,
        logger=logger,
        retry_message="Retrying PayPal payment verification...",
    )
    def verify_payment(self, transaction_id: str) -> bool:
        """Verify the status of a PayPal payment."""
        if not transaction_id or not isinstance(transaction_id, str):
            raise ValidationError("Invalid transaction_id", field="transaction_id", value=transaction_id)
        transaction = self.storage.get_transaction(transaction_id)
        if not transaction:
            logger.warning("PayPal transaction not found: " + transaction_id)
            return False
        try:
            access_token = self._get_access_token()
            order_id = transaction.metadata.get("paypal_order_id")
            if not order_id:
                logger.warning("No PayPal order ID in transaction metadata: " + transaction_id)
                return False
            order_resp = self._rate_limited_request(
                "GET",
                f"{self.api_base}/v2/checkout/orders/{order_id}",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {access_token}",
                },
                timeout=self.timeout,
            )

            # Handle specific HTTP errors
            if hasattr(order_resp, "status_code") and isinstance(order_resp.status_code, (int, float)):
                if order_resp.status_code == 404:
                    logger.warning(f"PayPal order {order_id} not found")
                    return False
                elif order_resp.status_code >= 500:
                    logger.error(f"PayPal server error: {order_resp.status_code}")
                    return False

            order_resp.raise_for_status()
            order = order_resp.json()
            status = order.get("status", "PENDING").lower()
            is_verified = status in ("completed", "approved", "captured")

            # Use consistent status mapping like capture_order
            status_mapping = {
                "completed": "completed",
                "approved": "completed",
                "captured": "completed",
                "pending": "pending",
                "declined": "failed",
                "expired": "failed",
                "voided": "cancelled",
                "cancelled": "cancelled",
            }
            new_status = status_mapping.get(status, "pending")

            # Get original status before modifying transaction
            original_status = transaction.status
            transaction.status = new_status

            # Update cache and storage with thread safety
            with self.transactions_lock:
                if transaction_id in self.transactions:
                    existing_transaction = self.transactions[transaction_id]
                    if existing_transaction.metadata.get("paypal_order_id") == transaction.metadata.get("paypal_order_id"):
                        logger.warning(
                            f"Transaction {transaction_id} already exists for order {transaction.metadata.get('paypal_order_id')}"
                        )
                        return is_verified
                    if existing_transaction.status != transaction.status:
                        logger.info(
                            f"Updating transaction {transaction_id} status from {existing_transaction.status} to {transaction.status}"
                        )
                self.transactions[transaction_id] = transaction

            # Only save if status changed to avoid unnecessary storage operations
            if original_status != new_status:
                try:
                    self.storage.save_transaction(transaction)
                except Exception as storage_error:
                    logger.error(f"Failed to save transaction to storage: {storage_error}")
                    # For production environments, log critical storage failure but don't fail verification
                    if not self.mock_mode and not self._is_dev_mode():
                        logger.critical(
                            f"CRITICAL: Payment verification succeeded but storage failed for transaction {transaction_id}"
                        )
                        # Add storage failure flag to transaction metadata
                        transaction.metadata["storage_failed"] = True
                        transaction.metadata["storage_error"] = str(storage_error)
                    # For mock/dev environments, continue with cached transaction
                    else:
                        logger.warning("Continuing with cached transaction due to storage failure (mock/dev mode)")

            logger.debug(f"PayPal payment verification for {transaction_id}: {is_verified}")
            return is_verified
        except PaymentFailed:
            # Re-raise payment failures as-is
            raise
        except requests.exceptions.Timeout:
            logger.error(f"PayPal API request timed out for verify_payment: {transaction_id}")
            raise PaymentFailed("PayPal API request timed out")
        except Exception as e:
            logger.error(f"Error verifying PayPal payment: {e}")
            raise ProviderError(f"PayPal payment verification error: {e}", provider="paypal")

    def verify_webhook_signature(self, payload: str, headers: dict) -> bool:
        """Verify the signature of a PayPal webhook event."""
        import json
        import re

        try:
            access_token = self._get_access_token()
            verify_url = f"{self.api_base}/v1/notifications/verify-webhook-signature"

            # Normalize header names to handle case sensitivity
            normalized_headers = {k.lower(): v for k, v in headers.items()}

            transmission_id = (
                headers.get("Paypal-Transmission-Id")
                or headers.get("PayPal-Transmission-Id")
                or normalized_headers.get("paypal-transmission-id")
            )
            transmission_time = (
                headers.get("Paypal-Transmission-Time")
                or headers.get("PayPal-Transmission-Time")
                or normalized_headers.get("paypal-transmission-time")
            )
            cert_url = (
                headers.get("Paypal-Cert-Url") or headers.get("PayPal-Cert-Url") or normalized_headers.get("paypal-cert-url")
            )
            auth_algo = (
                headers.get("Paypal-Auth-Algo") or headers.get("PayPal-Auth-Algo") or normalized_headers.get("paypal-auth-algo")
            )
            transmission_sig = (
                headers.get("Paypal-Transmission-Sig")
                or headers.get("PayPal-Transmission-Sig")
                or normalized_headers.get("paypal-transmission-sig")
            )
            webhook_id = (
                headers.get("Paypal-Webhook-Id")
                or headers.get("PayPal-Webhook-Id")
                or normalized_headers.get("paypal-webhook-id")
                or self.webhook_id
            )

            if not webhook_id:
                raise ProviderError("No webhook ID provided in headers or configuration.", provider="paypal")
            if not all(
                [
                    transmission_id,
                    transmission_time,
                    cert_url,
                    auth_algo,
                    transmission_sig,
                    webhook_id,
                ]
            ):
                raise ProviderError("Missing required PayPal webhook headers.", provider="paypal")

            # Validate transmission_time format (ISO 8601 format)
            if transmission_time and not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", transmission_time):
                raise ProviderError("Invalid PayPal webhook transmission_time format", provider="paypal")

            # Validate auth_algo
            if auth_algo != "SHA256withRSA":
                raise ProviderError("Unsupported PayPal webhook auth_algo", provider="paypal")

            verify_payload = {
                "auth_algo": auth_algo,
                "cert_url": cert_url,
                "transmission_id": transmission_id,
                "transmission_sig": transmission_sig,
                "transmission_time": transmission_time,
                "webhook_id": webhook_id,
                "webhook_event": (json.loads(payload) if isinstance(payload, str) else payload),
            }
            resp = self._rate_limited_request(
                "POST",
                verify_url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {access_token}",
                },
                json=verify_payload,
                timeout=self.timeout,
            )

            # Handle specific HTTP errors
            if hasattr(resp, "status_code") and isinstance(resp.status_code, (int, float)):
                if resp.status_code == 400:
                    try:
                        error_data = resp.json()
                        logger.warning(f"PayPal webhook verification failed: {error_data.get('message', 'Bad request')}")
                    except (ValueError, KeyError, TypeError) as json_error:
                        logger.error(
                            f"Failed to parse PayPal response: {json_error}, raw response: {getattr(resp, 'text', 'No response text')}"
                        )
                        logger.warning(f"PayPal webhook verification failed: Bad request (invalid response format)")
                    return False
                elif resp.status_code >= 500:
                    logger.error(f"PayPal server error during webhook verification: {resp.status_code}")
                    return False

            resp.raise_for_status()
            verification_status = resp.json().get("verification_status")
            if verification_status == "SUCCESS":
                return True
            else:
                logger.warning(f"PayPal webhook signature verification failed: {verification_status}")
                return False
        except requests.exceptions.Timeout:
            logger.error("PayPal API request timed out for webhook signature verification")
            raise ProviderError("PayPal API request timed out", provider="paypal")
        except Exception as e:
            logger.error(f"Error verifying PayPal webhook signature: {e}")
            raise ProviderError(
                f"PayPal webhook signature verification error: {e}",
                provider="paypal",
            )

    def handle_webhook(self, payload: str, headers: dict) -> None:
        """
        Handle PayPal webhook events and update transaction statuses.

        This method processes webhook events from PayPal and updates the corresponding
        PaymentTransaction records in storage. It handles CHECKOUT.ORDER.COMPLETED
        events to create or update transaction records.

        Args:
            payload: The webhook payload from PayPal
            headers: The webhook headers

        Raises:
            ProviderError: If webhook signature is invalid or processing fails
        """
        if not self.verify_webhook_signature(payload, headers):
            raise ProviderError("Invalid webhook signature", provider="paypal")

        try:
            import json

            event = json.loads(payload) if isinstance(payload, str) else payload
            event_type = event.get("event_type")

            if event_type == "CHECKOUT.ORDER.COMPLETED":
                with self.transactions_lock:
                    order = event["resource"]
                    order_id = order.get("id")
                    purchase_unit = order.get("purchase_units", [{}])[0]
                    user_id = purchase_unit.get("custom_id")
                    amount = float(purchase_unit.get("amount", {}).get("value", 0))
                    currency = purchase_unit.get("amount", {}).get("currency_code", "USD")
                    captures = purchase_unit.get("payments", {}).get("captures", [])
                    capture_id = captures[0].get("id") if captures else None

                    all_transactions = self.storage.list_transactions() if hasattr(self.storage, "list_transactions") else []
                    existing_transaction = None
                    for tx in all_transactions:
                        if tx.metadata.get("paypal_order_id") == order_id:
                            existing_transaction = tx
                            break

                    if existing_transaction:
                        _ = existing_transaction.status  # Store original status for potential future use
                        existing_transaction.status = "completed"
                        existing_transaction.completed_at = datetime.now(timezone.utc)
                        existing_transaction.metadata.update(
                            {
                                "paypal_capture_id": capture_id,
                                "webhook_processed": True,
                                "webhook_event_id": event.get("id"),
                                "webhook_event_type": event_type,
                            }
                        )
                        self.transactions[existing_transaction.id] = existing_transaction
                        try:
                            self.storage.save_transaction(existing_transaction)
                            logger.info(
                                f"Webhook processed: Updated transaction {existing_transaction.id} to completed for order {order_id}"
                            )
                        except Exception as storage_error:
                            logger.error(f"Failed to save completed transaction to storage: {storage_error}")
                            raise ProviderError(f"Failed to save completed transaction: {storage_error}", provider="paypal")
                    else:
                        if user_id:
                            transaction_id = str(uuid.uuid4())
                            now = datetime.now(timezone.utc)
                            transaction = PaymentTransaction(
                                id=transaction_id,
                                user_id=user_id,
                                amount=amount,
                                currency=currency,
                                payment_method="paypal",
                                status="completed",
                                created_at=now,
                                completed_at=now,
                                metadata={
                                    "paypal_order_id": order_id,
                                    "paypal_capture_id": capture_id,
                                    "paypal_environment": self.environment,
                                    "webhook_created": True,
                                    "webhook_event_id": event.get("id"),
                                    "webhook_event_type": event_type,
                                },
                            )
                            self.transactions[transaction_id] = transaction
                            try:
                                self.storage.save_transaction(transaction)
                                logger.info(f"Webhook fallback: Created transaction {transaction_id} for order {order_id}")
                            except Exception as storage_error:
                                logger.error(f"Failed to save webhook-created transaction to storage: {storage_error}")

            elif event_type == "CHECKOUT.ORDER.APPROVED":
                order = event["resource"]
                order_id = order.get("id")
                logger.debug(f"PayPal order approved: {order_id}")

            elif event_type == "CHECKOUT.ORDER.CANCELLED":
                with self.transactions_lock:
                    order = event["resource"]
                    order_id = order.get("id")
                    all_transactions = self.storage.list_transactions() if hasattr(self.storage, "list_transactions") else []
                    for tx in all_transactions:
                        if tx.metadata.get("paypal_order_id") == order_id and tx.status == "pending":
                            tx.status = "cancelled"
                            tx.metadata.update(
                                {
                                    "webhook_processed": True,
                                    "webhook_event_id": event.get("id"),
                                    "webhook_event_type": event_type,
                                }
                            )
                            self.transactions[tx.id] = tx
                            try:
                                self.storage.save_transaction(tx)
                                logger.info(f"Webhook processed: Updated transaction {tx.id} to cancelled for order {order_id}")
                            except Exception as storage_error:
                                logger.error(f"Failed to save cancelled transaction to storage: {storage_error}")

            elif event_type == "PAYMENT.CAPTURE.REFUNDED":
                with self.transactions_lock:
                    capture_id = event["resource"].get("id")
                    all_transactions = self.storage.list_transactions() if hasattr(self.storage, "list_transactions") else []
                    for tx in all_transactions:
                        if tx.metadata.get("paypal_capture_id") == capture_id:
                            tx.status = "refunded"
                            tx.metadata.update(
                                {
                                    "paypal_refund_id": event["resource"].get("id"),
                                    "webhook_processed": True,
                                    "webhook_event_id": event.get("id"),
                                    "webhook_event_type": event_type,
                                }
                            )
                            self.transactions[tx.id] = tx
                            try:
                                self.storage.save_transaction(tx)
                                logger.info(
                                    f"Webhook processed: Updated transaction {tx.id} to refunded for capture {capture_id}"
                                )
                            except Exception as storage_error:
                                logger.error(f"Failed to save refunded transaction to storage: {storage_error}")
                                raise ProviderError(f"Failed to save refunded transaction: {storage_error}", provider="paypal")

            elif event_type == "PAYMENT.CAPTURE.DENIED":
                with self.transactions_lock:
                    capture_id = event["resource"].get("id")
                    all_transactions = self.storage.list_transactions() if hasattr(self.storage, "list_transactions") else []
                    for tx in all_transactions:
                        if tx.metadata.get("paypal_capture_id") == capture_id:
                            tx.status = "failed"
                            tx.metadata.update(
                                {
                                    "webhook_processed": True,
                                    "webhook_event_id": event.get("id"),
                                    "webhook_event_type": event_type,
                                }
                            )
                            self.transactions[tx.id] = tx
                            try:
                                self.storage.save_transaction(tx)
                                logger.info(f"Webhook processed: Updated transaction {tx.id} to failed for capture {capture_id}")
                            except Exception as storage_error:
                                logger.error(f"Failed to save failed transaction to storage: {storage_error}")
                                raise ProviderError(f"Failed to save failed transaction: {storage_error}", provider="paypal")

            else:
                logger.debug(f"Unhandled PayPal webhook event type: {event_type}")

        except ImportError:
            logger.warning("json library not available for webhook processing")
            raise ProviderError("json library not available", provider="paypal")
        except Exception as e:
            logger.error(f"Error processing PayPal webhook: {e}")
            raise ProviderError(f"Webhook processing error: {e}", provider="paypal")

    def refund_payment(self, transaction_id: str, amount: float | None = None, idempotency_key: str | None = None) -> Any:
        """Refund a completed PayPal transaction."""
        transaction = self.storage.get_transaction(transaction_id)
        if not transaction:
            logger.warning(f"PayPal transaction not found for refund: {transaction_id}")
            raise ProviderError(f"Transaction {transaction_id} not found", provider="paypal")
        if transaction.status != "completed":
            logger.warning(f"Cannot refund incomplete transaction: {transaction_id}")
            raise ProviderError(
                f"Cannot refund incomplete transaction {transaction_id}",
                provider="paypal",
            )

        # Validate refund amount doesn't exceed transaction amount
        if amount is not None and amount > transaction.amount:
            logger.warning(f"Refund amount {amount} exceeds transaction amount {transaction.amount}")
            raise ValidationError(
                f"Refund amount {amount} exceeds transaction amount {transaction.amount}", field="amount", value=amount
            )
        try:
            access_token = self._get_access_token()
            capture_id = transaction.metadata.get("paypal_capture_id")
            if not capture_id:
                logger.warning(f"No PayPal capture ID in transaction metadata: {transaction_id}")
                raise ProviderError("No PayPal capture ID in transaction metadata", provider="paypal")
            refund_payload = (
                {
                    "amount": {
                        "value": f"{amount:.2f}".rstrip("0").rstrip(".") if amount == int(amount) else f"{amount:.2f}",
                        "currency_code": transaction.currency,
                    }
                }
                if amount is not None
                else {}
            )
            # Generate unique idempotency key with timestamp to avoid conflicts
            refund_amount_str = str(amount) if amount is not None else "full"
            idempotency_key = idempotency_key or self._generate_idempotency_key(transaction_id, amount or 0, refund_amount_str)
            refund_resp = self._rate_limited_request(
                "POST",
                f"{self.api_base}/v2/payments/captures/{capture_id}/refund",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {access_token}",
                    "PayPal-Request-Id": idempotency_key,
                },
                json=refund_payload if refund_payload else None,
                timeout=self.timeout,
            )

            # Handle specific HTTP errors
            if hasattr(refund_resp, "status_code") and isinstance(refund_resp.status_code, (int, float)):
                if refund_resp.status_code == 400:
                    try:
                        error_data = refund_resp.json()
                        raise ProviderError(
                            f"PayPal refund failed: {error_data.get('message', 'Bad request')}", provider="paypal"
                        )
                    except (ValueError, KeyError, TypeError) as json_error:
                        logger.error(
                            f"Failed to parse PayPal response: {json_error}, raw response: {getattr(refund_resp, 'text', 'No response text')}"
                        )
                        raise ProviderError(f"PayPal refund failed: Bad request (invalid response format)", provider="paypal")
                elif refund_resp.status_code == 403:
                    raise ProviderError("PayPal access forbidden. Check API permissions.", provider="paypal")
                elif refund_resp.status_code == 404:
                    raise ProviderError(f"PayPal capture {capture_id} not found", provider="paypal")
                elif refund_resp.status_code == 422:
                    raise ProviderError("PayPal request unprocessable. Check request format.", provider="paypal")
                elif refund_resp.status_code >= 500:
                    raise ProviderError(f"PayPal server error: {refund_resp.status_code}", provider="paypal")

            refund_resp.raise_for_status()
            try:
                refund = refund_resp.json()
            except (ValueError, KeyError, TypeError) as json_error:
                logger.error(
                    f"Failed to parse PayPal response: {json_error}, raw response: {getattr(refund_resp, 'text', 'No response text')}"
                )
                raise ProviderError(f"PayPal refund failed: Invalid response format", provider="paypal")
            refund_id = refund.get("id", "unknown_refund_id")
            refund_status = refund.get("status", "refunded").lower()
            refund_amount = float(refund.get("amount", {}).get("value", amount if amount is not None else transaction.amount))

            # Get original status before modifying transaction
            original_status = transaction.status
            transaction.status = "refunded"
            transaction.metadata["paypal_refund_id"] = refund_id
            transaction.metadata["refund_amount"] = refund_amount

            # Only save if status changed to avoid unnecessary storage operations
            if original_status != "refunded":
                try:
                    self.storage.save_transaction(transaction)
                except Exception as storage_error:
                    logger.error(f"Failed to save refunded transaction to storage: {storage_error}")
                    # Continue with the refund but log the error

            logger.info(
                f"PayPal refund succeeded: {refund_id} for transaction {transaction_id}, amount: {refund_amount} {transaction.currency}"
            )
            return {
                "refund_id": refund_id,
                "status": refund_status,
                "amount": refund_amount,
            }
        except PaymentFailed:
            # Re-raise payment failures as-is
            raise
        except requests.exceptions.Timeout:
            logger.error(f"PayPal API request timed out for refund_payment: {transaction_id}, {amount}, {refund_amount_str}")
            raise PaymentFailed("PayPal API request timed out")
        except Exception as e:
            logger.error(f"Error processing PayPal refund: {e}")
            raise ProviderError(f"PayPal refund error: {e}", provider="paypal")

    def get_payment_status(self, transaction_id: str) -> str:
        """Get the current status of a PayPal payment."""
        transaction = self.storage.get_transaction(transaction_id)
        if not transaction:
            logger.warning(f"PayPal transaction not found for status: {transaction_id}")
            raise ProviderError(f"Transaction {transaction_id} not found", provider="paypal")
        try:
            access_token = self._get_access_token()
            order_id = transaction.metadata.get("paypal_order_id")
            if not order_id:
                logger.warning(f"No PayPal order ID in transaction metadata: {transaction_id}")
                raise ProviderError("No PayPal order ID in transaction metadata", provider="paypal")
            order_resp = self._rate_limited_request(
                "GET",
                f"{self.api_base}/v2/checkout/orders/{order_id}",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {access_token}",
                },
                timeout=self.timeout,
            )

            # Handle specific HTTP errors
            if hasattr(order_resp, "status_code") and isinstance(order_resp.status_code, (int, float)):
                if order_resp.status_code == 404:
                    logger.warning(f"PayPal order {order_id} not found")
                    return transaction.status  # Return stored status if order not found
                elif order_resp.status_code >= 500:
                    logger.error(f"PayPal server error: {order_resp.status_code}")
                    return transaction.status  # Return stored status on server error

            order_resp.raise_for_status()
            try:
                order = order_resp.json()
            except (ValueError, KeyError, TypeError) as json_error:
                logger.error(
                    f"Failed to parse PayPal response: {json_error}, raw response: {getattr(order_resp, 'text', 'No response text')}"
                )
                return transaction.status  # Return stored status on parsing error

            status = order.get("status", "PENDING").lower()

            # Use consistent status mapping like capture_order
            status_mapping = {
                "completed": "completed",
                "approved": "completed",
                "captured": "completed",
                "pending": "pending",
                "declined": "failed",
                "expired": "failed",
                "voided": "cancelled",
                "cancelled": "cancelled",
            }
            new_status = status_mapping.get(status, "pending")

            # Get original status before modifying transaction
            original_status = transaction.status
            transaction.status = new_status

            # Update cache and storage with thread safety
            with self.transactions_lock:
                if transaction_id in self.transactions:
                    existing_transaction = self.transactions[transaction_id]
                    if existing_transaction.metadata.get("paypal_order_id") == transaction.metadata.get("paypal_order_id"):
                        logger.warning(
                            f"Transaction {transaction_id} already exists for order {transaction.metadata.get('paypal_order_id')}"
                        )
                        return new_status
                    if existing_transaction.status != transaction.status:
                        logger.info(
                            f"Updating transaction {transaction_id} status from {existing_transaction.status} to {transaction.status}"
                        )
                self.transactions[transaction_id] = transaction

            # Only save if status changed to avoid unnecessary storage operations
            if original_status != new_status:
                try:
                    self.storage.save_transaction(transaction)
                except Exception as storage_error:
                    logger.error(f"Failed to save transaction status to storage: {storage_error}")

            logger.debug(f"PayPal payment status for {transaction_id}: {new_status}")
            return new_status
        except PaymentFailed:
            # Re-raise payment failures as-is
            raise
        except requests.exceptions.Timeout:
            logger.error(f"PayPal API request timed out for get_payment_status: {transaction_id}")
            raise PaymentFailed("PayPal API request timed out")
        except Exception as e:
            logger.error(f"Error getting PayPal payment status: {e}")
            raise ProviderError(f"PayPal payment status error: {e}", provider="paypal")

    def health_check(self) -> bool:
        try:
            access_token = self._get_access_token()
            return bool(access_token)
        except Exception as e:
            logger.error(f"PayPal health check failed: {e}")
            return False

    def create_checkout_session(
        self,
        user_id: str,
        plan: Any,
        success_url: str,
        cancel_url: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """
        Create a PayPal checkout session for payment.

        Args:
            user_id: ID of the user making the payment
            plan: Payment plan or amount information
            success_url: URL to redirect to on successful payment
            cancel_url: URL to redirect to on cancelled payment
            metadata: Additional metadata for the session

        Returns:
            Dictionary containing session information (session_id, checkout_url)

        Raises:
            ProviderError: If session creation fails
            ValidationError: If parameters are invalid
        """
        # Extract amount and currency from plan
        if hasattr(plan, "price") and hasattr(plan, "currency"):
            amount = plan.price
            currency = plan.currency
        elif isinstance(plan, dict):
            amount = plan.get("price", 0)
            currency = plan.get("currency", "USD")
        else:
            raise ValidationError("Invalid plan format", field="plan", value=plan)

        # Create PayPal order
        order_response = self.create_order(
            user_id=user_id,
            amount=amount,
            currency=currency,
            return_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
        )

        # Extract approval URL from order response
        approval_url = None
        for link in order_response.get("links", []):
            if link.get("rel") == "approve":
                approval_url = link.get("href")
                break

        if not approval_url:
            raise ProviderError("No approval URL found in PayPal order response", provider="paypal")

        return {
            "session_id": order_response.get("id", ""),
            "checkout_url": approval_url,
        }

    def _is_dev_mode(self) -> bool:
        """Return True if running in a development or test environment."""
        return super()._is_dev_mode()

    def _validate_metadata(self, metadata):
        """Validate metadata to ensure it's a dictionary or None."""
        if metadata is not None and not isinstance(metadata, dict):
            raise ValidationError(
                f"Metadata must be a dictionary or None, got {type(metadata).__name__}",
                field="metadata",
                value=metadata,
            )
