"""
Custom exceptions for the AI Agent Payments SDK.

Defines all custom exceptions for payment errors, access control, and system errors.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class AIAgentPaymentsError(Exception):
    """Base exception for all AI Agent Payments SDK errors."""

    message: str
    error_code: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        logger.error(
            "%s: %s (Code: %s, Details: %s)",
            self.__class__.__name__,
            self.message,
            self.error_code,
            self.details,
        )

    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}" if self.error_code else self.message


@dataclass
class PaymentError(AIAgentPaymentsError):
    """Base exception for payment-related errors."""

    def __post_init__(self):
        super().__post_init__()
        logger.error("Payment Error: %s", self.message)


@dataclass
class PaymentFailed(PaymentError):
    """Raised when a payment transaction fails."""

    transaction_id: Optional[str] = None
    provider_error: Optional[str] = None

    def __post_init__(self):
        self.details.update(
            {
                k: v
                for k, v in {
                    "transaction_id": self.transaction_id,
                    "provider_error": self.provider_error,
                }.items()
                if v is not None
            }
        )
        self.error_code = self.error_code or "PAYMENT_FAILED"
        super().__post_init__()
        logger.error(
            "Payment Failed: %s (Transaction: %s, Provider: %s)",
            self.message,
            self.transaction_id,
            self.provider_error,
        )


@dataclass
class PaymentRequired(PaymentError):
    """Raised when payment is required but not provided."""

    feature: Optional[str] = None
    required_amount: Optional[float] = None

    def __post_init__(self):
        self.details.update(
            {
                k: v
                for k, v in {
                    "feature": self.feature,
                    "required_amount": self.required_amount,
                }.items()
                if v is not None
            }
        )
        self.error_code = self.error_code or "PAYMENT_REQUIRED"
        super().__post_init__()
        logger.warning(
            "Payment Required: %s (Feature: %s, Amount: %s)",
            self.message,
            self.feature,
            self.required_amount,
        )


@dataclass
class InvalidPaymentMethod(PaymentError):
    """Raised when an invalid payment method is used."""

    payment_method: Optional[str] = None
    supported_methods: Optional[list] = None

    def __post_init__(self):
        self.details.update(
            {
                k: v
                for k, v in {
                    "payment_method": self.payment_method,
                    "supported_methods": self.supported_methods,
                }.items()
                if v is not None
            }
        )
        self.error_code = self.error_code or "INVALID_PAYMENT_METHOD"
        super().__post_init__()
        logger.warning(
            "Invalid Payment Method: %s (Method: %s, Supported: %s)",
            self.message,
            self.payment_method,
            self.supported_methods,
        )


@dataclass
class AccessControlError(AIAgentPaymentsError):
    """Base exception for access control violations."""

    def __post_init__(self):
        self.error_code = self.error_code or "ACCESS_CONTROL_ERROR"
        super().__post_init__()
        logger.warning("Access Control Error: %s", self.message)


@dataclass
class UsageLimitExceeded(AccessControlError):
    """Raised when a user exceeds their usage limits."""

    feature: Optional[str] = None
    current_usage: Optional[int] = None
    limit: Optional[int] = None

    def __post_init__(self):
        self.details.update(
            {
                k: v
                for k, v in {
                    "feature": self.feature,
                    "current_usage": self.current_usage,
                    "limit": self.limit,
                }.items()
                if v is not None
            }
        )
        self.error_code = self.error_code or "USAGE_LIMIT_EXCEEDED"
        super().__post_init__()


@dataclass
class SubscriptionExpired(AccessControlError):
    """Raised when a user's subscription has expired."""

    subscription_id: Optional[str] = None
    plan_id: Optional[str] = None
    expired_date: Optional[str] = None

    def __post_init__(self):
        self.details.update(
            {
                k: v
                for k, v in {
                    "subscription_id": self.subscription_id,
                    "plan_id": self.plan_id,
                    "expired_date": self.expired_date,
                }.items()
                if v is not None
            }
        )
        self.error_code = self.error_code or "SUBSCRIPTION_EXPIRED"
        super().__post_init__()


@dataclass
class FeatureNotAvailable(AccessControlError):
    """Raised when a feature is not available to the user."""

    feature: Optional[str] = None
    plan_id: Optional[str] = None
    available_features: Optional[list] = None

    def __post_init__(self):
        self.details.update(
            {
                k: v
                for k, v in {
                    "feature": self.feature,
                    "plan_id": self.plan_id,
                    "available_features": self.available_features,
                }.items()
                if v is not None
            }
        )
        self.error_code = self.error_code or "FEATURE_NOT_AVAILABLE"
        super().__post_init__()


@dataclass
class StorageError(AIAgentPaymentsError):
    """Base exception for storage backend errors."""

    storage_type: Optional[str] = None
    operation: Optional[str] = None
    entity_id: Optional[str] = None

    def __post_init__(self):
        self.details.update(
            {
                k: v
                for k, v in {
                    "storage_type": self.storage_type,
                    "operation": self.operation,
                    "entity_id": self.entity_id,
                }.items()
                if v is not None
            }
        )
        self.error_code = self.error_code or "STORAGE_ERROR"
        super().__post_init__()


@dataclass
class ConfigurationError(AIAgentPaymentsError):
    """Raised for configuration errors."""

    config_key: Optional[str] = None
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None

    def __post_init__(self):
        self.details.update(
            {
                k: v
                for k, v in {
                    "config_key": self.config_key,
                    "expected_value": self.expected_value,
                    "actual_value": self.actual_value,
                }.items()
                if v is not None
            }
        )
        self.error_code = self.error_code or "CONFIGURATION_ERROR"
        super().__post_init__()


@dataclass
class ValidationError(AIAgentPaymentsError):
    """Raised for validation errors."""

    field: Optional[str] = None
    value: Any = None
    constraints: Optional[dict[str, Any]] = None

    def __post_init__(self):
        self.details.update(
            {
                k: v
                for k, v in {
                    "field": self.field,
                    "value": self.value,
                    "constraints": self.constraints,
                }.items()
                if v is not None
            }
        )
        self.error_code = self.error_code or "VALIDATION_ERROR"
        super().__post_init__()


@dataclass
class ProviderError(AIAgentPaymentsError):
    """Raised for errors from payment providers."""

    provider: Optional[str] = None
    provider_error_code: Optional[str] = None
    provider_error_message: Optional[str] = None

    def __post_init__(self):
        self.details.update(
            {
                k: v
                for k, v in {
                    "provider": self.provider,
                    "provider_error_code": self.provider_error_code,
                    "provider_error_message": self.provider_error_message,
                }.items()
                if v is not None
            }
        )
        self.error_code = self.error_code or "PROVIDER_ERROR"
        super().__post_init__()
