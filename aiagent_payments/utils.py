"""
Utility functions for the AI Agent Payments SDK.

This module contains reusable utility functions and decorators for retry logic, validation, formatting, and other common operations.
"""

import importlib.util
import logging
import random
import re
import time
import uuid
from calendar import monthrange
from collections.abc import Callable
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Optional, TypeVar, Union

# Import SecretRedactor from logging_config for explicit redaction
from .logging_config import SecretRedactor

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Module-level SecretRedactor instance for consistent redaction
_secret_redactor = SecretRedactor()


def redact_message(msg: str) -> str:
    """Consistent message redaction function for the entire module."""
    try:
        # Use module-level redactor for consistency and efficiency
        for pattern in _secret_redactor.SECRET_PATTERNS:
            msg = pattern.sub(lambda m: m.group(1) + "***REDACTED***", msg)
        return msg
    except Exception:
        # Enhanced fallback: specific regex for payment-related secrets with minimum length requirements
        patterns = [
            # Stripe secret keys: sk_test_ or sk_live_ followed by at least 24 chars
            (r"sk_(test|live)_[a-zA-Z0-9]{24,}", "sk_***REDACTED***"),
            # Bearer tokens: at least 20 chars to avoid short test tokens
            (r"Bearer [a-zA-Z0-9\-_\.]{20,}", "Bearer ***REDACTED***"),
            # API keys: at least 20 chars to avoid short test keys
            (r"api_key=[a-zA-Z0-9\-_\.]{20,}", "api_key=***REDACTED***"),
            # PayPal client IDs: start with A and at least 20 chars
            (r"client_id=A[a-zA-Z0-9\-_]{20,}", "client_id=***REDACTED***"),
            # Client secrets: at least 20 chars to avoid short test secrets
            (r"client_secret=[a-zA-Z0-9\-_]{20,}", "client_secret=***REDACTED***"),
            # Ethereum addresses: exactly 64 hex chars after 0x
            (r"0x[a-fA-F0-9]{64}", "0x***REDACTED***"),
            # Stripe webhook secrets: whsec_ followed by at least 24 chars
            (r"whsec_[a-zA-Z0-9]{24,}", "whsec_***REDACTED***"),
            # Stripe payment intents: pi_ followed by at least 24 chars
            (r"pi_[a-zA-Z0-9]{24,}", "pi_***REDACTED***"),
            # Stripe charges: ch_ followed by at least 24 chars
            (r"ch_[a-zA-Z0-9]{24,}", "ch_***REDACTED***"),
        ]
        for pattern, replacement in patterns:
            msg = re.sub(pattern, replacement, msg)
        return msg


# Build default exceptions list with payment provider support
_default_exceptions = [ConnectionError, TimeoutError]

# Conditionally add payment provider exceptions if available
if importlib.util.find_spec("stripe"):
    try:
        from stripe.error import APIError, RateLimitError  # type: ignore

        _default_exceptions.extend([APIError, RateLimitError])
    except ImportError as e:
        logger.warning("Failed to import stripe exceptions: %s", redact_message(str(e)))

if importlib.util.find_spec("paypalrestsdk"):
    try:
        from paypalrestsdk.exceptions import ClientError, ServerError  # type: ignore

        _default_exceptions.extend([ClientError, ServerError])
    except ImportError as e:
        logger.warning("Failed to import PayPal exceptions: %s", redact_message(str(e)))

if importlib.util.find_spec("web3"):
    try:
        # Handle circular import issues with web3 and Python 3.13
        import sys

        if sys.version_info >= (3, 13):
            # For Python 3.13+, use a more defensive import approach
            try:
                from web3.exceptions import Web3Exception  # type: ignore

                _default_exceptions.append(Web3Exception)
            except (ImportError, AttributeError) as e:
                logger.warning("Failed to import web3 exceptions (Python 3.13 compatibility): %s", redact_message(str(e)))
        else:
            from web3.exceptions import Web3Exception  # type: ignore

            _default_exceptions.append(Web3Exception)
    except ImportError as e:
        logger.warning("Failed to import web3 exceptions: %s", redact_message(str(e)))

DEFAULT_RETRY_EXCEPTIONS = tuple(_default_exceptions)

# Static set of valid ISO 4217 codes and common stablecoins
VALID_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY", "SEK", "NZD", "USDC", "USDT", "DAI", "BUSD", "GUSD"}


def generate_id(prefix: str = "") -> str:
    """Generate a unique identifier with an optional prefix."""
    return f"{prefix}{uuid.uuid4()}" if prefix else str(uuid.uuid4())


def validate_currency(currency: str, provider: Optional[Any] = None) -> bool:
    """
    Return True if currency is a valid ISO 4217 or supported stablecoin code.

    Args:
        currency: The currency code to validate
        provider: Optional payment provider instance to check runtime support

    Note: For stablecoins, verify that your payment provider supports the chosen currency.
    If provider is provided and has get_supported_currencies method, runtime validation is performed.
    Raises ValueError if provider lacks currency support information.
    """
    # Basic format validation
    if not (
        isinstance(currency, str)
        and len(currency) == 3
        and currency.isalpha()
        and currency.isupper()
        and currency in VALID_CURRENCIES
    ):
        return False

    # Runtime provider validation if provider is provided
    if provider is not None:
        try:
            # Check if provider has get_supported_currencies method
            if hasattr(provider, "get_supported_currencies"):
                supported_currencies = provider.get_supported_currencies()
                if currency not in supported_currencies:
                    logger.debug("Currency %s not supported by provider %s", currency, type(provider).__name__)
                    return False
            # Alternative: check if provider has supported_currencies attribute
            elif hasattr(provider, "supported_currencies"):
                if currency not in provider.supported_currencies:
                    logger.debug("Currency %s not supported by provider %s", currency, type(provider).__name__)
                    return False
            else:
                logger.error("Provider %s lacks currency support information", type(provider).__name__)
                raise ValueError(f"Provider {type(provider).__name__} does not provide currency support information")
        except Exception as e:
            logger.error("Failed to check provider currency support: %s", redact_message(str(e)))
            raise ValueError(f"Currency validation failed for provider {type(provider).__name__}: {redact_message(str(e))}")

    return True


def validate_amount(amount: Union[int, float]) -> bool:
    """Return True if amount is a non-negative number."""
    return isinstance(amount, (int, float)) and amount >= 0 and not (isinstance(amount, float) and not (amount == amount))


def format_currency(amount: Union[int, float], currency: str = "USD", provider: Optional[Any] = None) -> str:
    """
    Format an amount with currency code. Returns fallback string on error.

    Args:
        amount: The amount to format
        currency: The currency code
        provider: Optional payment provider for runtime currency validation
    """
    try:
        if not validate_amount(amount):
            raise ValueError(f"Invalid amount: {amount}")
        if not validate_currency(currency, provider):
            raise ValueError(f"Invalid or unsupported currency: {currency}")
        return f"{amount:.2f} {currency}"
    except ValueError as e:
        logger.error(f"Failed to format currency: {redact_message(str(e))}")
        return "Invalid amount/currency"


def parse_datetime(datetime_str: str) -> Optional[datetime]:
    """Parse an ISO datetime string to a datetime object, or None if invalid."""
    if not isinstance(datetime_str, str) or not re.match(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?([+-]\d{2}:\d{2}|Z)?", datetime_str
    ):
        return None
    try:
        dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        # Comprehensive semantic validation with month-specific day limits
        if (
            dt.year < 1970
            or dt.year > 9999
            or dt.month < 1
            or dt.month > 12
            or dt.day < 1
            or dt.day > monthrange(dt.year, dt.month)[1]
            or dt.hour < 0
            or dt.hour > 23
            or dt.minute < 0
            or dt.minute > 59
            or dt.second < 0
            or dt.second > 59
        ):
            logger.debug("Invalid datetime components: %s", redact_message(datetime_str))
            return None
        return dt
    except (ValueError, TypeError) as e:
        logger.debug("Invalid datetime format: %s", redact_message(str(e)))
        return None


def get_current_timestamp() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def retry(
    exceptions: Union[type[Exception], tuple[type[Exception], ...]] = DEFAULT_RETRY_EXCEPTIONS,
    max_attempts: int = 3,
    initial_delay: float = 0.5,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    logger: Optional[logging.Logger] = None,
    retry_message: Optional[str] = None,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
):
    """
    Decorator to retry a function on specified exceptions with exponential backoff.
    Sensitive data in exception messages is always redacted.
    Recommended exceptions: ConnectionError, TimeoutError, payment provider API errors.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if initial_delay < 0:
        raise ValueError("initial_delay must be non-negative")
    if backoff_factor < 1:
        raise ValueError("backoff_factor must be at least 1")
    if max_delay < initial_delay:
        raise ValueError("max_delay must be at least initial_delay")

    # Exclude critical system exceptions from retrying
    if isinstance(exceptions, type) and exceptions is Exception:
        exceptions = DEFAULT_RETRY_EXCEPTIONS
    safe_exceptions = tuple(
        exc
        for exc in (exceptions if isinstance(exceptions, tuple) else (exceptions,))
        if not issubclass(exc, (KeyboardInterrupt, SystemExit, MemoryError, ValueError, TypeError))
    )
    if not safe_exceptions:
        raise ValueError("No retryable exceptions provided after excluding critical/logic errors")

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except safe_exceptions as e:
                    last_exception = e
                    redacted_msg = redact_message(str(e))
                    if attempt == max_attempts:
                        if logger:
                            logger.error(
                                "Function %s failed after %d attempts: %s",
                                func.__name__,
                                max_attempts,
                                redacted_msg,
                            )
                        try:
                            raise type(e)(redacted_msg).with_traceback(e.__traceback__)
                        except Exception:
                            # If instantiation fails, re-raise the original exception
                            raise e
                    actual_delay = min(delay, max_delay)
                    if jitter:
                        actual_delay *= 0.75 + random.random() * 0.5
                    if logger:
                        message = retry_message or f"Retrying {func.__name__}..."
                        logger.warning(
                            "%s (attempt %d/%d, delay %.2fs): %s",
                            message,
                            attempt,
                            max_attempts,
                            actual_delay,
                            redacted_msg,
                        )
                    if on_retry:
                        try:
                            on_retry(attempt, e)
                        except Exception as callback_error:
                            redacted_callback_msg = redact_message(str(callback_error))
                            if logger:
                                logger.warning("Retry callback failed: %s", redacted_callback_msg)
                    time.sleep(actual_delay)
                    delay *= backoff_factor
            raise RuntimeError(f"Function {func.__name__} failed unexpectedly") from last_exception

        return wrapper

    return decorator


def parse_email(email: str) -> Optional[str]:
    """
    Return the email if valid, else None.
    Input is validated against strict regex; no sensitive data is logged.
    """
    if not isinstance(email, str):
        return None
    email = email.strip()
    # Stricter regex for email validation
    if re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        return email
    return None


def sanitize_string(value: Any, max_length: int = 255) -> str:
    """
    Sanitize a string value for storage or display. Unicode-safe, validates max_length.
    Input is not logged raw to prevent sensitive data leaks; output is safe for use.
    """
    if max_length <= 0:
        raise ValueError("max_length must be positive")
    s = str(value) if value is not None else ""
    # Unicode-safe truncation
    encoded = s.encode("utf-8")[:max_length]
    return encoded.decode("utf-8", errors="ignore")


def deep_get(data: dict, key_path: str, default: Any = None) -> Any:
    """Get a nested value from a dict using dot notation. Type safe."""
    if not isinstance(data, dict):
        return default
    keys = key_path.split(".")
    for key in keys:
        if isinstance(data, dict) and key in data:
            data = data[key]
        else:
            return default
    return data


def deep_set(data: dict, key_path: str, value: Any) -> None:
    """Set a nested value in a dict using dot notation. Type safe."""
    if not isinstance(data, dict):
        raise ValueError("data must be a dictionary")
    keys = key_path.split(".")
    for key in keys[:-1]:
        if key not in data or not isinstance(data[key], dict):
            data[key] = {}
        data = data[key]
    data[keys[-1]] = value


def sanitize_log_message(message: str) -> str:
    """
    Global log sanitization function. In production, this should mask or remove sensitive data from log messages.
    For now, it returns the message unchanged.
    """
    # TODO: Implement masking of sensitive data for production
    return message
