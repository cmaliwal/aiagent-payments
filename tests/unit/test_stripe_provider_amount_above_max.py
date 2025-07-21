import sys
import types

import pytest

from aiagent_payments.providers.stripe import StripeProvider


def test_stripe_provider_amount_above_max():
    class DummyPaymentIntent:
        def __init__(self):
            self.id = "pi_test_123"
            self.status = "requires_payment_method"
            self.amount = 1000000000
            self.currency = "usd"

    def mock_create(*args, **kwargs):
        return DummyPaymentIntent()

    def mock_retrieve(*args, **kwargs):
        return DummyPaymentIntent()

    # Patch sys.modules['stripe'] with a ModuleType
    stripe_mod = types.ModuleType("stripe")
    payment_intent_mod = types.SimpleNamespace(create=mock_create, retrieve=mock_retrieve)
    setattr(stripe_mod, "PaymentIntent", payment_intent_mod)
    sys.modules["stripe"] = stripe_mod
    p = StripeProvider(api_key="sk_test_dummy")
    transaction = p.process_payment("user1", 1_000_000, "USD")
    assert transaction.metadata["stripe_payment_intent_id"] == "pi_test_123"
    assert transaction.status == "pending"
