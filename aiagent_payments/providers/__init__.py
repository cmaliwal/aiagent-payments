"""
Payment providers for the AI Agent Payments SDK.

This module provides various payment providers including mock, crypto, stripe, and PayPal.
"""

import logging
from typing import Dict, List, Optional, Type

from aiagent_payments.config import ENABLED_PROVIDERS

from .base import PaymentProvider

logger = logging.getLogger(__name__)

# Import providers conditionally to avoid circular imports
try:
    from .mock import MockProvider
except ImportError:
    MockProvider = None

try:
    from .stripe import StripeProvider
except ImportError:
    StripeProvider = None

try:
    from .paypal import PayPalProvider
except ImportError:
    PayPalProvider = None

# Crypto provider is imported conditionally due to web3 circular import issues
CryptoProvider = None

# Provider registry
PROVIDERS: Dict[str, Type[PaymentProvider]] = {}

if MockProvider:
    PROVIDERS["mock"] = MockProvider

if StripeProvider:
    PROVIDERS["stripe"] = StripeProvider

if PayPalProvider:
    PROVIDERS["paypal"] = PayPalProvider

# Add crypto provider to registry when available
if "crypto" in ENABLED_PROVIDERS:
    try:
        from .crypto import CryptoProvider as CryptoProviderClass

        CryptoProvider = CryptoProviderClass
        PROVIDERS["crypto"] = CryptoProvider
    except ImportError as e:
        logger.warning(f"CryptoProvider not available: {e}")
        CryptoProvider = None


# Crypto provider is added dynamically when needed
def _get_crypto_provider():
    """
    Get CryptoProvider class, importing it only when needed.

    Args:
        wallet_address: The wallet address to validate
        infura_project_id: The Infura project ID to validate
        confirmations_required: The number of confirmations required
        max_gas_price_gwei: The maximum gas price in Gwei

    Raises:
        ValueError: If any required parameters are missing or invalid
    """
    global CryptoProvider
    if CryptoProvider is None:
        try:
            from .crypto import CryptoProvider as CryptoProviderClass

            CryptoProvider = CryptoProviderClass
        except ImportError as e:
            error_msg = f"Failed to import CryptoProvider: {e}. This may be due to missing web3 dependencies."
            logger.error(error_msg)
            raise ValueError(error_msg) from e
    return CryptoProvider


def _validate_provider_availability(provider_type: str) -> None:
    """
    Validate that an enabled provider is actually available.

    Args:
        provider_type: The type of provider to validate

    Raises:
        ValueError: If the provider is enabled but not available
    """
    provider_available = False

    if provider_type == "mock":
        provider_available = MockProvider is not None
    elif provider_type == "stripe":
        provider_available = StripeProvider is not None
    elif provider_type == "paypal":
        provider_available = PayPalProvider is not None
    elif provider_type == "crypto":
        try:
            _get_crypto_provider()
            provider_available = True
        except ValueError:
            provider_available = False

    if not provider_available:
        error_msg = (
            f"Provider '{provider_type}' is enabled in configuration but not available. "
            f"This may be due to missing dependencies or import errors. "
            f"Please check your installation and dependencies."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)


def _validate_crypto_config(
    wallet_address: Optional[str],
    infura_project_id: Optional[str],
    confirmations_required: Optional[int],
    max_gas_price_gwei: Optional[float],
) -> None:
    """
    Validate CryptoProvider configuration parameters.

    Args:
        wallet_address: The wallet address to validate
        infura_project_id: The Infura project ID to validate
        confirmations_required: The number of confirmations required
        max_gas_price_gwei: The maximum gas price in Gwei

    Raises:
        ValueError: If any required parameters are missing or invalid
    """
    if not wallet_address or not isinstance(wallet_address, str):
        raise ValueError("wallet_address is required for CryptoProvider and must be a non-empty string")

    if not wallet_address.startswith("0x") or len(wallet_address) != 42:
        raise ValueError("wallet_address must be a valid Ethereum address (0x followed by 40 hex characters)")

    if not infura_project_id or not isinstance(infura_project_id, str):
        raise ValueError("infura_project_id is required for CryptoProvider and must be a non-empty string")

    if confirmations_required is not None:
        if not isinstance(confirmations_required, int) or confirmations_required <= 0:
            raise ValueError("confirmations_required must be a positive integer if provided")

    if max_gas_price_gwei is not None:
        if not isinstance(max_gas_price_gwei, (int, float)) or max_gas_price_gwei <= 0:
            raise ValueError("max_gas_price_gwei must be a positive number if provided")


def _validate_stripe_config(api_key: str) -> None:
    """
    Validate StripeProvider configuration parameters.

    Args:
        api_key: The Stripe API key to validate

    Raises:
        ValueError: If the API key is invalid or uses mock values
    """
    if not api_key or not isinstance(api_key, str):
        raise ValueError("api_key is required for StripeProvider and must be a non-empty string")

    # Reject mock/default values in non-test environments
    if api_key in ["sk_test_mock_key", "mock_key", "test_key"]:
        raise ValueError(
            "Invalid Stripe API key: Using mock/test key. " "Please provide a valid Stripe API key for beta testing."
        )

    # Basic validation for Stripe API key format
    if not api_key.startswith(("sk_test_", "sk_live_")):
        raise ValueError("Invalid Stripe API key format. " "Stripe API keys should start with 'sk_test_' or 'sk_live_'")


def _validate_paypal_config(client_id: str, client_secret: str, sandbox: bool) -> None:
    """
    Validate PayPalProvider configuration parameters.

    Args:
        client_id: The PayPal client ID to validate
        client_secret: The PayPal client secret to validate
        sandbox: The sandbox flag to validate

    Raises:
        ValueError: If any required parameters are missing or invalid
    """
    if not client_id or not isinstance(client_id, str):
        raise ValueError("client_id is required for PayPalProvider and must be a non-empty string")

    if not client_secret or not isinstance(client_secret, str):
        raise ValueError("client_secret is required for PayPalProvider and must be a non-empty string")

    # Reject mock/default values
    if client_id in ["mock_client_id", "test_client_id"] or client_secret in ["mock_client_secret", "test_client_secret"]:
        raise ValueError(
            "Invalid PayPal credentials: Using mock/test credentials. "
            "Please provide valid PayPal client_id and client_secret for beta testing."
        )

    if not isinstance(sandbox, bool):
        raise ValueError("sandbox parameter must be a boolean value")


__all__ = ["PaymentProvider", "create_payment_provider"]
if "mock" in ENABLED_PROVIDERS:
    __all__.append("MockProvider")
if "crypto" in ENABLED_PROVIDERS:
    __all__.append("CryptoProvider")
if "stripe" in ENABLED_PROVIDERS:
    __all__.append("StripeProvider")
if "paypal" in ENABLED_PROVIDERS:
    __all__.append("PayPalProvider")

globals_ = globals()
if "mock" not in ENABLED_PROVIDERS and "MockProvider" in globals_:
    del globals_["MockProvider"]
if "crypto" not in ENABLED_PROVIDERS and "CryptoProvider" in globals_:
    del globals_["CryptoProvider"]
if "stripe" not in ENABLED_PROVIDERS and "StripeProvider" in globals_:
    del globals_["StripeProvider"]
if "paypal" not in ENABLED_PROVIDERS and "PayPalProvider" in globals_:
    del globals_["PayPalProvider"]


def create_payment_provider(provider_type: str, **kwargs) -> PaymentProvider:
    """
    Factory function to create payment providers.

    Args:
        provider_type: Type of payment provider (mock, crypto, stripe, paypal)
        **kwargs: Additional arguments for the provider

    Returns:
        PaymentProvider: The created payment provider

    Raises:
        ValueError: If provider type is not supported or configuration is invalid
    """
    provider_type = provider_type.lower()

    # Enhanced provider availability validation
    if provider_type not in ENABLED_PROVIDERS:
        logger.error(f"Provider '{provider_type}' is disabled in configuration.")
        raise ValueError(f"Provider '{provider_type}' is disabled in configuration.")

    _validate_provider_availability(provider_type)

    if provider_type == "mock":
        success_rate = kwargs.get("success_rate", 1.0)
        if not isinstance(success_rate, (int, float)) or not (0.0 <= success_rate <= 1.0):
            raise ValueError("success_rate must be a number between 0.0 and 1.0")
        logger.info("Creating MockProvider with success rate: " + str(success_rate))
        return MockProvider(success_rate=success_rate)  # type: ignore - validated by _validate_provider_availability

    elif provider_type == "crypto":
        crypto_provider_class = _get_crypto_provider()
        wallet_address = kwargs.get("wallet_address")
        infura_project_id = kwargs.get("infura_project_id")
        network = kwargs.get("network", "mainnet")
        confirmations_required = kwargs.get("confirmations_required")
        max_gas_price_gwei = kwargs.get("max_gas_price_gwei")
        storage = kwargs.get("storage")

        _validate_crypto_config(wallet_address, infura_project_id, confirmations_required, max_gas_price_gwei)

        # Validate network parameter
        if network not in ["mainnet", "goerli", "sepolia"]:
            raise ValueError("network must be one of: mainnet, goerli, sepolia")

        logger.info("Creating CryptoProvider for USDT")
        return crypto_provider_class(
            wallet_address=wallet_address,  # type: ignore - validated by _validate_crypto_config
            infura_project_id=infura_project_id,  # type: ignore - validated by _validate_crypto_config
            network=network,
            confirmations_required=confirmations_required,
            max_gas_price_gwei=max_gas_price_gwei,
            storage=storage,
        )

    elif provider_type == "stripe":
        api_key = kwargs.get("api_key")
        webhook_secret = kwargs.get("webhook_secret")
        storage = kwargs.get("storage")

        _validate_stripe_config(api_key)  # type: ignore - validation function handles None case

        logger.info("Creating StripeProvider")
        return StripeProvider(api_key=api_key, webhook_secret=webhook_secret, storage=storage)  # type: ignore - validated by _validate_stripe_config

    elif provider_type == "paypal":
        client_id = kwargs.get("client_id")
        client_secret = kwargs.get("client_secret")
        sandbox = kwargs.get("sandbox", True)
        return_url = kwargs.get("return_url")
        cancel_url = kwargs.get("cancel_url")
        webhook_id = kwargs.get("webhook_id")
        timeout = kwargs.get("timeout", 30)

        _validate_paypal_config(client_id, client_secret, sandbox)  # type: ignore - validation function handles None cases

        logger.info("Creating PayPalProvider for " + ("sandbox" if sandbox else "live") + " environment")
        return PayPalProvider(
            client_id=client_id,
            client_secret=client_secret,
            sandbox=sandbox,
            return_url=return_url,
            cancel_url=cancel_url,
            webhook_id=webhook_id,
            timeout=timeout,
        )  # type: ignore - validated by _validate_paypal_config

    else:
        raise ValueError(f"Unsupported provider type: {provider_type}")
