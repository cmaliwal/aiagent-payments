#!/usr/bin/env python3
"""
Advanced Usage Example for AI Agent Payments SDK

This example demonstrates advanced features including:
- Comprehensive logging configuration
- Error handling and recovery
- Multiple payment providers
- Advanced subscription management
- Usage analytics and reporting
- Performance monitoring
"""

import os
import time

from aiagent_payments import (
    BillingPeriod,
    PaymentManager,
    PaymentPlan,
    PaymentType,
    UsageLimitExceeded,
)
from aiagent_payments.providers import create_payment_provider
from aiagent_payments.providers.mock import MockProvider
from aiagent_payments.providers.paypal import PayPalProvider
from aiagent_payments.providers.stripe import StripeProvider

# Import crypto provider conditionally to handle web3 circular import issues
try:
    from aiagent_payments.providers.crypto import CryptoProvider
except ImportError as e:
    print(f"Warning: Could not import CryptoProvider: {e}")
    CryptoProvider = None
from aiagent_payments.exceptions import PaymentFailed, PaymentRequired
from aiagent_payments.logging_config import get_logger, log_performance, setup_logging
from aiagent_payments.storage.file import FileStorage


def setup_advanced_logging():
    """Set up comprehensive logging for the example."""
    # Configure logging with file output and colors
    setup_logging(
        level="DEBUG",
        log_file="aiagent_payments_example.log",
        use_colors=True,
        include_timestamp=True,
    )

    # Get a structured logger for this example
    logger = get_logger(__name__)
    logger.info("Advanced logging configured successfully")
    return logger


def create_payment_plans(payment_manager: PaymentManager) -> dict[str, str]:
    """Create various payment plans for demonstration."""
    logger = get_logger(__name__)

    plans = {}

    # Freemium plan
    freemium_plan = PaymentPlan(
        id="freemium",
        name="Freemium",
        description="Free tier with limited usage",
        payment_type=PaymentType.FREEMIUM,
        price=0.01,  # Minimum price required by validation
        free_requests=10,
        features=["basic_ai_response", "simple_analysis"],
    )
    payment_manager.create_payment_plan(freemium_plan)
    plans["freemium"] = freemium_plan.id
    logger.info(f"Created freemium plan: {freemium_plan.name}")

    # Pay-per-use plan
    pay_per_use_plan = PaymentPlan(
        id="pay_per_use",
        name="Pay Per Use",
        description="Pay only for what you use",
        payment_type=PaymentType.PAY_PER_USE,
        price=0.01,  # Minimum price required by validation
        price_per_request=0.10,
        currency="USD",
        features=["advanced_ai_response", "complex_analysis", "custom_models"],
    )
    payment_manager.create_payment_plan(pay_per_use_plan)
    plans["pay_per_use"] = pay_per_use_plan.id
    logger.info(f"Created pay-per-use plan: {pay_per_use_plan.name}")

    # Monthly subscription
    monthly_plan = PaymentPlan(
        id="monthly_pro",
        name="Monthly Pro",
        description="Unlimited access with monthly billing",
        payment_type=PaymentType.SUBSCRIPTION,
        price=29.99,
        currency="USD",
        billing_period=BillingPeriod.MONTHLY,
        requests_per_period=1000,
        features=[
            "advanced_ai_response",
            "complex_analysis",
            "custom_models",
            "priority_support",
        ],
    )
    payment_manager.create_payment_plan(monthly_plan)
    plans["monthly"] = monthly_plan.id
    logger.info(f"Created monthly subscription plan: {monthly_plan.name}")

    # Annual subscription
    annual_plan = PaymentPlan(
        id="annual_enterprise",
        name="Annual Enterprise",
        description="Enterprise features with annual billing",
        payment_type=PaymentType.SUBSCRIPTION,
        price=299.99,
        currency="USD",
        billing_period=BillingPeriod.YEARLY,
        requests_per_period=10000,
        features=[
            "advanced_ai_response",
            "complex_analysis",
            "custom_models",
            "priority_support",
            "api_access",
            "white_label",
        ],
    )
    payment_manager.create_payment_plan(annual_plan)
    plans["annual"] = annual_plan.id
    logger.info(f"Created annual subscription plan: {annual_plan.name}")

    return plans


def demonstrate_payment_providers():
    """Demonstrate different payment providers."""
    logger = get_logger(__name__)

    providers = {}

    # Mock provider for testing
    mock_provider = MockProvider(success_rate=0.95)
    providers["mock"] = mock_provider
    logger.info("Created mock provider with 95% success rate")

    # CryptoProvider demo (only if available and API keys are present)
    if CryptoProvider is None:
        print("[SKIP] CryptoProvider demo skipped: CryptoProvider not available (web3 import issue)")
        crypto_provider = None
    else:
        infura_project_id = os.getenv("INFURA_PROJECT_ID")
        wallet_address = os.getenv("WALLET_ADDRESS")
        if not infura_project_id or not wallet_address:
            print("[SKIP] CryptoProvider demo skipped: INFURA_PROJECT_ID and/or WALLET_ADDRESS not set.")
            print("To enable, set both environment variables with your own API keys.")
            crypto_provider = None
        else:
            crypto_provider = CryptoProvider(
                wallet_address=wallet_address, infura_project_id=infura_project_id, network="sepolia"  # Use testnet for demo
            )
            print("[OK] CryptoProvider initialized.")
    providers["crypto"] = crypto_provider
    if crypto_provider:
        logger.info("Created USDT crypto provider (Ethereum via Infura)")
    else:
        logger.info("Crypto provider not available")

    # Example: Process, check status, and refund a crypto payment
    if crypto_provider is not None:
        # For USDT ERC-20, you must provide sender_address in metadata
        crypto_transaction = crypto_provider.process_payment(
            user_id="test_user",
            amount=0.001,
            currency="USD",
            metadata={"sender_address": "0xabcdef1234567890abcdef1234567890abcdef12"},
        )
        logger.info(f"Send crypto payment to: {crypto_transaction.metadata['wallet_address']}")
        status = crypto_provider.get_payment_status(crypto_transaction.id)
        logger.info(f"Crypto payment status: {status}")
        # For E2E demo: set transaction status to 'completed' to allow refund
        crypto_transaction.status = "completed"  # E2E/demo only; do not use in production
        crypto_refund = crypto_provider.refund_payment(crypto_transaction.id, amount=0.001)
        logger.info(f"Crypto refund result: {crypto_refund}")
        # Note: Refunds are manual unless you provide wallet integration. No private keys are handled by the SDK.

    # Stripe provider (mock mode or real Stripe if API key is set)
    stripe_provider = StripeProvider(api_key="sk_test_mock_key")  # Use your real key for live payments
    providers["stripe"] = stripe_provider
    logger.info("Created Stripe provider in mock mode (set real API key for live payments)")

    # For E2E demo: patch Stripe API calls to avoid real network requests
    import unittest.mock as mock

    with (
        mock.patch("stripe.PaymentIntent.create") as mock_create,
        mock.patch("stripe.PaymentIntent.retrieve") as mock_retrieve,
        mock.patch("stripe.Refund.create") as mock_refund,
    ):
        # Mock PaymentIntent creation
        mock_payment_intent = mock.Mock()
        mock_payment_intent.id = "pi_123"
        mock_payment_intent.status = "succeeded"
        mock_create.return_value = mock_payment_intent
        # Mock PaymentIntent retrieve and charges
        mock_charge = mock.Mock()
        mock_charge.id = "ch_123"
        mock_payment_intent.charges = mock.Mock()
        mock_payment_intent.charges.data = [mock_charge]
        mock_retrieve.return_value = mock_payment_intent
        # Mock Refund creation
        mock_refund.return_value = mock.Mock(id="re_123", status="succeeded", amount=500)
        # Example: Process, check status, and refund a payment (mock or real)
        transaction = stripe_provider.process_payment(user_id="test_user", amount=20.0, currency="USD")
        status = stripe_provider.get_payment_status(transaction.id)
        logger.info(f"Stripe payment status: {status}")
        # For E2E demo: set transaction status to 'completed' to allow refund
        transaction.status = "completed"  # E2E/demo only; do not use in production
        refund = stripe_provider.refund_payment(transaction.id, amount=5)
        logger.info(f"Stripe refund result: {refund}")

    # PayPal provider (mock mode or real PayPal if credentials are set)
    paypal_provider = PayPalProvider(
        client_id="mock_client_id",  # Use your real client_id for live payments
        client_secret="mock_client_secret",  # Use your real client_secret for live payments
        sandbox=True,
        return_url="https://example.com/return",  # Required for validation
        cancel_url="https://example.com/cancel",  # Required for validation
    )
    providers["paypal"] = paypal_provider
    logger.info("Created PayPal provider in sandbox/mock mode (set real credentials for live payments)")

    # For E2E demo: patch PayPal API calls to avoid real network requests
    # Note: Since requests is imported inside PayPalProvider methods, we patch it at the module level
    with (
        mock.patch("requests.post") as mock_post,
        mock.patch("requests.get") as mock_get,
        mock.patch("requests.Session.post") as mock_session_post,
        mock.patch("requests.Session.get") as mock_session_get,
    ):
        # Mock OAuth token response
        mock_oauth_resp = mock.Mock()
        mock_oauth_resp.raise_for_status.return_value = None
        mock_oauth_resp.json.return_value = {"access_token": "fake_token"}
        # Mock order creation response (for create_order)
        mock_order_resp = mock.Mock()
        mock_order_resp.raise_for_status.return_value = None
        mock_order_resp.json.return_value = {
            "id": "ORDER123",
            "status": "CREATED",
            "links": [{"href": "https://www.sandbox.paypal.com/checkoutnow?token=ORDER123", "rel": "approve", "method": "GET"}],
        }
        # Mock capture response (for capture_order)
        mock_capture_resp = mock.Mock()
        mock_capture_resp.raise_for_status.return_value = None
        mock_capture_resp.json.return_value = {
            "id": "ORDER123",
            "status": "COMPLETED",
            "purchase_units": [
                {
                    "payments": {
                        "captures": [
                            {
                                "id": "CAPTURE123",
                                "amount": {"value": "20.00", "currency_code": "USD"},
                                "update_time": "2024-01-01T12:00:00Z",
                            }
                        ]
                    }
                }
            ],
        }
        # Mock refund response
        mock_refund_resp = mock.Mock()
        mock_refund_resp.raise_for_status.return_value = None
        mock_refund_resp.json.return_value = {"status": "COMPLETED", "id": "REFUND123"}

        # Use a function-based side effect to handle any number of PayPal API calls
        def paypal_post_side_effect(*args, **kwargs):
            url = args[0] if args else ""
            print(f"[MOCK] PayPal POST called: {url}")  # Log every URL for debug
            if "oauth2/token" in url:
                return mock_oauth_resp
            elif "/v2/checkout/orders" in url and "capture" not in url:
                return mock_order_resp
            elif "capture" in url:
                return mock_capture_resp
            elif "refund" in url:
                return mock_refund_resp
            return mock_oauth_resp

        def paypal_get_side_effect(*args, **kwargs):
            url = args[0] if args else ""
            print(f"[MOCK] PayPal GET called: {url}")  # Log every URL for debug
            # All GETs for order status return completed
            return mock_status_resp

        mock_post.side_effect = paypal_post_side_effect
        mock_session_post.side_effect = paypal_post_side_effect
        mock_get.side_effect = paypal_get_side_effect
        mock_session_get.side_effect = paypal_get_side_effect
        # Mock order status response for requests.get
        mock_status_resp = mock.Mock()
        mock_status_resp.raise_for_status.return_value = None
        mock_status_resp.json.return_value = {"status": "COMPLETED"}
        # Patch PayPalProvider._get_access_token to always return the fake token
        with mock.patch.object(PayPalProvider, "_get_access_token", return_value="fake_token"):
            # Example: Two-step PayPal flow
            order_response = paypal_provider.create_order(
                user_id="test_user",
                amount=20.0,
                currency="USD",
                return_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )
            approval_link = None
            for link in order_response.get("links", []):
                if link.get("rel") == "approve":
                    approval_link = link.get("href")
                    break
            logger.info(f"PayPal order created. Approval link: {approval_link}")
            # Simulate user approval and capture
            paypal_transaction = paypal_provider.capture_order(user_id="test_user", order_id=order_response["id"])
            paypal_transaction.status = "completed"  # E2E/demo only; do not use in production
            status = paypal_provider.get_payment_status(paypal_transaction.id)
            logger.info(f"PayPal payment status: {status}")
            refund = paypal_provider.refund_payment(paypal_transaction.id, amount=5)
            logger.info(f"PayPal refund result: {refund}")

    return providers


def demonstrate_crypto_features():
    """Demonstrate USDT crypto provider features."""
    logger = get_logger(__name__)

    # Check if crypto provider is available
    if CryptoProvider is None:
        logger.info("Crypto features skipped: CryptoProvider not available (web3 import issue)")
        return

    infura_project_id = os.getenv("INFURA_PROJECT_ID")
    wallet_address = os.getenv("WALLET_ADDRESS")

    if not infura_project_id or not wallet_address:
        logger.info("Crypto features skipped: INFURA_PROJECT_ID and/or WALLET_ADDRESS not set")
        return

    try:
        # Initialize crypto provider
        crypto_provider = CryptoProvider(
            wallet_address=wallet_address, infura_project_id=infura_project_id, network="sepolia"  # Use testnet for demo
        )

        logger.info("=== USDT Crypto Provider Features ===")

        # Get network information
        network_info = crypto_provider.get_network_info()
        logger.info(f"Network: {network_info.get('name')}")
        logger.info(f"Chain ID: {network_info.get('chain_id')}")
        logger.info(f"Block Height: {network_info.get('block_height')}")

        # Get USDT balance
        balance_info = crypto_provider.get_usdt_balance()
        logger.info(f"USDT Balance: {balance_info.get('balance')}")

        # Get provider capabilities
        capabilities = crypto_provider.get_capabilities()
        logger.info(f"Supports refunds: {capabilities.supports_refunds}")
        logger.info(f"Supported currencies: {capabilities.supported_currencies}")

    except Exception as e:
        logger.error(f"Error demonstrating crypto features: {str(e)}")


def demonstrate_user_scenarios(payment_manager: PaymentManager, plans: dict[str, str]):
    """Demonstrate various user scenarios."""
    logger = get_logger(__name__)

    users = {
        "freemium_user": "user_freemium_001",
        "pay_per_use_user": "user_pay_001",
        "monthly_user": "user_monthly_001",
        "annual_user": "user_annual_001",
    }

    # Scenario 1: Freemium user
    logger.info("=== Scenario 1: Freemium User ===")
    user_id = users["freemium_user"]

    # Use free features
    for i in range(5):
        try:
            result = payment_manager.check_access(user_id, "basic_ai_response")
            logger.info(f"  Freemium user access to basic_ai_response: {result}")

            if result:
                payment_manager.record_usage(user_id, "basic_ai_response")
                logger.info("  Recorded usage for freemium user")
        except Exception as e:
            logger.error(f"  Error for freemium user: {str(e)}")

    # Try to access premium feature (should fail)
    try:
        result = payment_manager.check_access(user_id, "custom_models")
        logger.info(f"  Freemium user access to custom_models: {result}")
    except Exception as e:
        logger.warning(f"  Expected failure for freemium user: {str(e)}")

    # Scenario 2: Pay-per-use user
    logger.info("=== Scenario 2: Pay-per-use User ===")
    user_id = users["pay_per_use_user"]

    # Use premium features (should trigger payment)
    for i in range(3):
        try:
            result = payment_manager.check_access(user_id, "custom_models")
            logger.info(f"  Pay-per-use user access to custom_models: {result}")

            if result:
                payment_manager.record_usage(user_id, "custom_models", cost=0.10)
                logger.info("  Recorded usage for pay-per-use user")
        except PaymentRequired as e:
            logger.info(f"  Payment required: {str(e)}")
            # In a real app, you would redirect to payment
        except Exception as e:
            logger.error(f"  Error for pay-per-use user: {str(e)}")

    # Scenario 3: Monthly subscription user
    logger.info("=== Scenario 3: Monthly Subscription User ===")
    user_id = users["monthly_user"]

    # Subscribe to monthly plan
    try:
        subscription = payment_manager.subscribe_user(user_id, plans["monthly"])
        logger.info(f"  Created monthly subscription: {subscription.id}")

        # Use premium features
        for i in range(5):
            result = payment_manager.check_access(user_id, "priority_support")
            logger.info(f"  Monthly user access to priority_support: {result}")

            if result:
                payment_manager.record_usage(user_id, "priority_support")
                logger.info("  Recorded usage for monthly user")
    except Exception as e:
        logger.error(f"  Error for monthly user: {str(e)}")

    # Scenario 4: Annual subscription user
    logger.info("=== Scenario 4: Annual Subscription User ===")
    user_id = users["annual_user"]

    # Subscribe to annual plan
    try:
        subscription = payment_manager.subscribe_user(user_id, plans["annual"])
        logger.info(f"  Created annual subscription: {subscription.id}")

        # Use enterprise features
        for i in range(10):
            result = payment_manager.check_access(user_id, "white_label")
            logger.info(f"  Annual user access to white_label: {result}")

            if result:
                payment_manager.record_usage(user_id, "white_label")
                logger.info("  Recorded usage for annual user")
    except Exception as e:
        logger.error(f"  Error for annual user: {str(e)}")


def demonstrate_analytics(payment_manager: PaymentManager, users: dict[str, str]):
    """Demonstrate analytics and reporting features."""
    logger = get_logger(__name__)

    logger.info("=== Analytics and Reporting ===")

    # Get usage for each user
    for user_type, user_id in users.items():
        logger.info(f"  --- {user_type.upper()} ---")

        # Get recent usage
        usage_records = payment_manager.get_user_usage(user_id)
        logger.info(f"    Total usage records: {len(usage_records):d}")

        # Get subscription info
        subscription = payment_manager.get_user_subscription(user_id)
        if subscription:
            logger.info(f"    Active subscription: {subscription.plan_id}")
            logger.info(f"    Usage count: {subscription.usage_count}")
            logger.info(f"    Days remaining: {subscription.get_days_remaining()}")
        else:
            logger.info("    No active subscription")

        # Calculate total cost
        total_cost = payment_manager.usage_tracker.get_total_cost(user_id)
        logger.info(f"    Total cost: ${float(total_cost):.2f}")

    # List all payment plans
    plans = payment_manager.list_payment_plans()
    logger.info("  --- Available Payment Plans ---")
    for plan in plans:
        logger.info(f"    {plan.id}: {plan.name} (${float(plan.price):.2f} {plan.currency})")


def demonstrate_error_handling():
    """Demonstrate error handling and recovery."""
    logger = get_logger(__name__)

    logger.info("=== Error Handling Demonstration ===")

    # Create a payment manager with a failing provider
    failing_provider = MockProvider(success_rate=0.0)
    payment_manager = PaymentManager(payment_provider=failing_provider)

    # Try to process a payment (should fail)
    try:
        transaction = payment_manager.process_payment("test_user", 10.0)
        logger.info(f"  Payment processed successfully: {transaction.id}")
    except PaymentFailed as e:
        logger.warning(f"  Expected payment failure: {str(e)}")
    except Exception as e:
        logger.error(f"  Unexpected error: {str(e)}")

    # Test usage limit exceeded
    try:
        # Create a plan with very low limits
        limited_plan = PaymentPlan(
            id="limited",
            name="Limited Plan",
            payment_type=PaymentType.FREEMIUM,
            free_requests=1,
            features=["test_feature"],
        )
        payment_manager.create_payment_plan(limited_plan)

        # Try to use more than allowed
        user_id = "limit_test_user"
        for i in range(3):
            try:
                result = payment_manager.check_access(user_id, "test_feature")
                if result:
                    payment_manager.record_usage(user_id, "test_feature")
                    logger.info(f"  Used feature {i + 1:d} times")
            except UsageLimitExceeded as e:
                logger.warning(f"  Expected usage limit exceeded: {str(e)}")
                break
    except Exception as e:
        logger.error(f"  Error in usage limit test: {str(e)}")


def main():
    """Main function demonstrating advanced SDK features."""
    start_time = time.time()

    # Set up logging
    logger = setup_advanced_logging()
    logger.info(f"Starting Advanced AI Agent Payments SDK Demo")

    try:
        # Create payment manager with file storage
        # Use absolute path to ensure consistent data location
        import os

        demo_data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "demo_data")
        storage = FileStorage(demo_data_path)
        payment_manager = PaymentManager(storage=storage)
        logger.info(f"Created payment manager with file storage")

        # Create payment plans
        plans = create_payment_plans(payment_manager)
        logger.info(f"Created {len(plans)} payment plans")

        # Demonstrate payment providers
        providers = demonstrate_payment_providers()
        logger.info(f"Demonstrated {len(providers):d} payment providers")

        # Demonstrate crypto features
        demonstrate_crypto_features()

        # Demonstrate user scenarios
        users = {
            "freemium_user": "user_freemium_001",
            "pay_per_use_user": "user_pay_001",
            "monthly_user": "user_monthly_001",
            "annual_user": "user_annual_001",
        }
        demonstrate_user_scenarios(payment_manager, plans)

        # Demonstrate analytics
        demonstrate_analytics(payment_manager, users)

        # Demonstrate error handling
        demonstrate_error_handling()

        # Performance logging
        end_time = time.time()
        log_performance("main", start_time, end_time, logger)

        logger.info("Advanced demo completed successfully!")

    except Exception as e:
        logger.error(f"Demo failed with error: {str(e)}")
        raise


if __name__ == "__main__":
    main()
