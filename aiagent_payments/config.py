"""
Configuration module for the AI Agent Payments SDK.

Handles environment-based configuration for storage backends and payment providers.
"""

import logging
import os
from typing import List

logger = logging.getLogger(__name__)

# Default configuration values
DEFAULT_ENABLED_STORAGE = "memory,file,database"
DEFAULT_ENABLED_PROVIDERS = "mock,crypto,stripe,paypal"

# Valid storage backends and payment providers
VALID_STORAGE_BACKENDS = {"memory", "file", "database"}
VALID_PAYMENT_PROVIDERS = {"mock", "crypto", "stripe", "paypal"}

# Supported currencies for validation
SUPPORTED_CURRENCIES = {
    # Fiat currencies
    "USD",
    "EUR",
    "GBP",
    "CAD",
    "AUD",
    "JPY",
    "CHF",
    "SEK",
    "NOK",
    "DKK",
    # Stablecoins
    "USDC",
    "USDT",
    "DAI",
    "BUSD",
    "TUSD",
    "FRAX",
    "GUSD",
    "LUSD",
    "SUSD",
    # Crypto (for crypto provider)
    "BTC",
    "ETH",
    "BNB",
    "ADA",
    "DOT",
    "LINK",
    "UNI",
    "LTC",
    "BCH",
    "XRP",
}

# Minimum amounts for currencies (in their respective units)
MINIMUM_AMOUNTS = {
    # Fiat currencies (in cents/smallest unit)
    "USD": 0.01,
    "EUR": 0.01,
    "GBP": 0.01,
    "CAD": 0.01,
    "AUD": 0.01,
    "JPY": 1,
    "CHF": 0.01,
    "SEK": 0.01,
    "NOK": 0.01,
    "DKK": 0.01,
    # Stablecoins (minimum amounts for payment providers)
    "USDC": 0.50,
    "USDT": 0.50,
    "DAI": 0.50,
    "BUSD": 0.50,
    "TUSD": 0.50,
    "FRAX": 0.50,
    "GUSD": 0.50,
    "LUSD": 0.50,
    "SUSD": 0.50,
    # Crypto (minimum amounts)
    "BTC": 0.0001,
    "ETH": 0.001,
    "BNB": 0.001,
    "ADA": 1,
    "DOT": 0.1,
    "LINK": 0.1,
    "UNI": 0.01,
    "LTC": 0.001,
    "BCH": 0.001,
    "XRP": 1,
}

# Configuration limits
MAX_CONFIG_STRING_LENGTH = 1000  # Maximum length for config strings
MAX_CONFIG_VALUES = 20  # Maximum number of values in a config list


def _validate_config_string(config_string: str, config_name: str) -> str:
    """Validate configuration string for type, length, and content."""
    if not isinstance(config_string, str):
        raise TypeError(f"{config_name} must be a string, got {type(config_string).__name__}")

    if len(config_string) > MAX_CONFIG_STRING_LENGTH:
        raise ValueError(f"{config_name} string too long ({len(config_string)} chars). Max: {MAX_CONFIG_STRING_LENGTH}")

    # Check for potentially malicious content
    if any(char in config_string for char in ["\0", "\r", "\n", "\t"]):
        raise ValueError(f"{config_name} contains invalid characters")

    return config_string


def _normalize_config_list(config_string: str, valid_values: set[str], config_name: str) -> List[str]:
    """Normalize and validate a comma-separated configuration string."""
    if not config_string:
        return []

    # Validate the input string
    config_string = _validate_config_string(config_string, config_name)

    values = [s.strip().lower() for s in config_string.split(",") if s.strip()]

    # Check for maximum number of values
    if len(values) > MAX_CONFIG_VALUES:
        raise ValueError(f"Too many {config_name} values ({len(values)}). Max: {MAX_CONFIG_VALUES}")

    invalid_values = [v for v in values if v not in valid_values]

    if invalid_values:
        raise ValueError(
            f"Invalid {config_name} values: {invalid_values}. " f"Valid values are: {', '.join(sorted(valid_values))}"
        )

    return values


def _get_enabled_storage() -> List[str]:
    """Get enabled storage backends from environment variables."""
    try:
        config_string = os.getenv("AIAgentPayments_EnabledStorage", DEFAULT_ENABLED_STORAGE)
        return _normalize_config_list(config_string, VALID_STORAGE_BACKENDS, "storage backends")
    except Exception as e:
        logger.error("Failed to parse storage configuration: %s. Using safe default.", e)
        return ["memory"]


def _get_enabled_providers() -> List[str]:
    """Get enabled payment providers from environment variables."""
    try:
        config_string = os.getenv("AIAgentPayments_EnabledProviders", DEFAULT_ENABLED_PROVIDERS)
        return _normalize_config_list(config_string, VALID_PAYMENT_PROVIDERS, "payment providers")
    except Exception as e:
        logger.error("Failed to parse provider configuration: %s. Using safe default.", e)
        return ["mock"]


# Initialize configuration with comprehensive error handling
try:
    ENABLED_STORAGE = _get_enabled_storage()
    ENABLED_PROVIDERS = _get_enabled_providers()

    # Ensure we have at least one storage and one provider
    if not ENABLED_STORAGE:
        logger.warning("No storage backends enabled. Using memory storage as fallback.")
        ENABLED_STORAGE = ["memory"]

    if not ENABLED_PROVIDERS:
        logger.warning("No payment providers enabled. Using mock provider as fallback.")
        ENABLED_PROVIDERS = ["mock"]

except Exception as e:
    logger.error("Critical configuration error: %s. Using safe defaults.", e)
    ENABLED_STORAGE = ["memory"]
    ENABLED_PROVIDERS = ["mock"]


def is_storage_enabled(storage_name: str) -> bool:
    """Check if a specific storage backend is enabled."""
    if not isinstance(storage_name, str):
        return False
    return storage_name.lower() in ENABLED_STORAGE


def is_provider_enabled(provider_name: str) -> bool:
    """Check if a specific payment provider is enabled."""
    if not isinstance(provider_name, str):
        return False
    return provider_name.lower() in ENABLED_PROVIDERS


def get_config_summary() -> dict:
    """Get a summary of the current configuration."""
    return {
        "enabled_storage": ENABLED_STORAGE,
        "enabled_providers": ENABLED_PROVIDERS,
        "valid_storage_backends": list(VALID_STORAGE_BACKENDS),
        "valid_payment_providers": list(VALID_PAYMENT_PROVIDERS),
    }
