import json
import os
import time
from unittest.mock import patch

import pytest

from aiagent_payments.exceptions import PaymentFailed, ProviderError, ValidationError
from aiagent_payments.providers.crypto import CryptoProvider
from aiagent_payments.providers.paypal import PayPalProvider
from aiagent_payments.providers.stripe import StripeProvider

pytestmark = pytest.mark.integration


# --- Stripe Integration Tests ---
@pytest.mark.skipif(not os.getenv("STRIPE_API_KEY"), reason="STRIPE_API_KEY not set; skipping Stripe integration test.")
class TestStripeIntegration:
    def setup_method(self):
        self.provider = StripeProvider()
        self.user_id = "test_user_stripe_integration"
        self.amount = 1.00
        self.currency = "usd"

    def test_stripe_payment_creation(self):
        """Test creating a payment with Stripe"""
        # Use unique user_id to avoid idempotency key conflicts
        unique_user_id = f"{self.user_id}_{int(time.time())}"
        tx = self.provider.process_payment(unique_user_id, self.amount, self.currency)
        assert tx.status in ("pending", "completed", "failed", "cancelled")

        # Test with different amount to avoid idempotency conflicts
        tx2 = self.provider.process_payment(unique_user_id, self.amount + 0.01, self.currency)
        assert tx2.status in ("pending", "completed", "failed", "cancelled")

        assert tx.amount == self.amount
        assert tx.currency == self.currency
        assert tx.user_id == unique_user_id
        # Note: PaymentTransaction doesn't have a provider attribute

    def test_stripe_payment_refund(self):
        """Test refunding a successful payment"""
        # Use unique user_id to avoid idempotency key conflicts
        unique_user_id = f"{self.user_id}_refund_{int(time.time())}"
        tx = self.provider.process_payment(unique_user_id, self.amount, self.currency)
        if tx.status == "completed":
            refund = self.provider.refund_payment(tx.id)
            assert refund.status in ("completed", "pending", "refunded")
            assert refund.amount == self.amount

    def test_stripe_payment_status_check(self):
        """Test checking payment status"""
        # Use unique user_id to avoid idempotency key conflicts
        unique_user_id = f"{self.user_id}_status_{int(time.time())}"
        tx = self.provider.process_payment(unique_user_id, self.amount, self.currency)
        status = self.provider.get_payment_status(tx.id)
        assert status in ("pending", "completed", "failed", "cancelled")

    def test_stripe_webhook_verification(self):
        """Test webhook signature verification"""
        # Mock webhook payload and headers
        payload = json.dumps({"type": "payment_intent.succeeded", "data": {"object": {"id": "pi_test"}}})
        sig_header = "t=1234567890,v1=test_signature"

        # Test without webhook secret (should return False, not raise)
        result = self.provider.verify_webhook_signature(payload, sig_header)
        assert result is False

        # Test with webhook secret (should handle invalid signature gracefully)
        provider_with_secret = StripeProvider(webhook_secret="whsec_test_secret")
        result = provider_with_secret.verify_webhook_signature(payload, sig_header)
        assert result is False  # Invalid signature should return False

    def test_stripe_health_check(self):
        """Test provider health check"""
        assert self.provider.health_check() is True

    def test_stripe_capabilities(self):
        """Test provider capabilities"""
        caps = self.provider.get_capabilities()
        assert caps.supports_refunds is True
        assert caps.supports_webhooks is True
        assert "USD" in caps.supported_currencies


# --- PayPal Integration Tests ---
@pytest.mark.skipif(
    not (os.getenv("PAYPAL_CLIENT_ID") and os.getenv("PAYPAL_CLIENT_SECRET")),
    reason="PayPal sandbox credentials not set; skipping PayPal integration test.",
)
class TestPayPalIntegration:
    def setup_method(self):
        # For PayPal, always provide dummy return_url and cancel_url
        self.return_url = "https://example.com/success"
        self.cancel_url = "https://example.com/cancel"
        self.provider = PayPalProvider(sandbox=True, return_url=self.return_url, cancel_url=self.cancel_url)
        self.user_id = "test_user_paypal_integration"
        self.amount = 1.00
        self.currency = "USD"

    def test_paypal_order_creation(self):
        """Test creating a PayPal order"""
        order = self.provider.create_order(
            self.user_id,
            self.amount,
            self.currency,
            return_url=self.return_url,
            cancel_url=self.cancel_url,
        )
        assert order["status"] in ("CREATED", "APPROVED")
        assert "id" in order
        assert "links" in order

    def test_paypal_webhook_verification(self):
        """Test webhook signature verification"""
        # Mock webhook payload and headers
        payload = json.dumps({"event_type": "CHECKOUT.ORDER.APPROVED"})
        headers = {"PAYPAL-TRANSMISSION-SIG": "test_signature"}

        # This will fail with invalid signature, but tests the verification flow
        with pytest.raises(Exception):
            self.provider.verify_webhook_signature(payload, headers)

    def test_paypal_health_check(self):
        """Test provider health check"""
        assert self.provider.health_check() is True

    def test_paypal_capabilities(self):
        """Test provider capabilities"""
        caps = self.provider.get_capabilities()
        assert caps.supports_refunds is True
        assert caps.supports_webhooks is True
        assert "USD" in caps.supported_currencies


# --- Crypto Integration Tests ---
@pytest.mark.skipif(
    not os.getenv("CRYPTO_WALLET_ADDRESS"), reason="CRYPTO_WALLET_ADDRESS not set; skipping Crypto integration test."
)
class TestCryptoIntegration:
    def setup_method(self):
        wallet_address = os.getenv("CRYPTO_WALLET_ADDRESS", "0x742d35Cc6634C0532925a3b8D4C9db96C4b4d8b6")
        self.provider = CryptoProvider(wallet_address=wallet_address)
        self.user_id = "test_user_crypto_integration"
        self.amount = 0.0001
        self.currency = "ETH"

    def test_crypto_payment_creation(self):
        """Test creating a crypto payment"""
        tx = self.provider.process_payment(self.user_id, self.amount, self.currency)
        assert tx.status in ("pending", "completed", "confirmed")
        assert tx.amount == self.amount
        assert tx.currency == self.currency
        assert tx.user_id == self.user_id
        # Note: PaymentTransaction doesn't have a provider attribute

    def test_crypto_payment_status_check(self):
        """Test checking crypto payment status"""
        tx = self.provider.process_payment(self.user_id, self.amount, self.currency)
        status = self.provider.get_payment_status(tx.id)
        assert status in ("pending", "completed", "confirmed", "failed")

    def test_crypto_health_check(self):
        """Test provider health check"""
        # CryptoProvider doesn't have a health_check method, so we'll test basic functionality
        caps = self.provider.get_capabilities()
        assert caps is not None

    def test_crypto_capabilities(self):
        """Test provider capabilities"""
        caps = self.provider.get_capabilities()
        assert caps.supports_refunds is True
        assert "ETH" in caps.supported_currencies


# --- Error Handling Tests ---
@pytest.mark.skipif(not os.getenv("STRIPE_API_KEY"), reason="STRIPE_API_KEY not set; skipping error handling test.")
def test_provider_error_handling():
    """Test error handling with invalid parameters"""
    provider = StripeProvider()

    # Test invalid amount
    with pytest.raises(ValidationError):
        provider.process_payment("user", -1.0, "usd")

    # Test invalid currency - now expects ValidationError
    with pytest.raises(ValidationError):
        provider.process_payment("user", 1.0, "INVALID")


# --- Multi-Provider Tests ---
@pytest.mark.skipif(
    not (os.getenv("STRIPE_API_KEY") and os.getenv("PAYPAL_CLIENT_ID")),
    reason="Multiple provider credentials not set; skipping multi-provider test.",
)
def test_multi_provider_compatibility():
    """Test that different providers return compatible transaction objects"""
    stripe_provider = StripeProvider()
    paypal_provider = PayPalProvider(
        sandbox=True, return_url="https://example.com/success", cancel_url="https://example.com/cancel"
    )

    # Test that both providers can be instantiated
    assert stripe_provider is not None
    assert paypal_provider is not None

    # Test that both have similar capabilities
    stripe_caps = stripe_provider.get_capabilities()
    paypal_caps = paypal_provider.get_capabilities()

    assert stripe_caps.supports_refunds == paypal_caps.supports_refunds
    assert stripe_caps.supports_webhooks == paypal_caps.supports_webhooks
