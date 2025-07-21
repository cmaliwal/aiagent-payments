"""
Data models for the AI Agent Payments SDK.

Defines core data structures for payment plans, subscriptions, usage records, and transactions.
"""

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .config import MINIMUM_AMOUNTS, SUPPORTED_CURRENCIES
from .exceptions import ValidationError
from .utils import sanitize_log_message

logger = logging.getLogger(__name__)


def _validate_json_serializable(obj: Any, field_name: str, path: str = "") -> None:
    """Validate that an object is JSON serializable, including nested elements."""
    if obj is None:
        return
    elif isinstance(obj, (str, int, float, bool)):
        return
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            item_path = f"{path}[{i}]" if path else f"[{i}]"
            _validate_json_serializable(item, field_name, item_path)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            item_path = f"{path}.{key}" if path else key
            _validate_json_serializable(value, field_name, item_path)
    else:
        raise ValidationError(
            f"Metadata contains non-JSON-serializable object at {path}: {type(obj).__name__}", field=field_name, value=obj
        )


def _validate_string_field(value: str, field_name: str, max_length: int = 255) -> None:
    """Validate and sanitize string fields with comprehensive security checks."""
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string", field=field_name, value=value)

    if len(value.strip()) == 0:
        raise ValidationError(f"{field_name} cannot be empty", field=field_name, value=value)

    if len(value) > max_length:
        raise ValidationError(f"{field_name} exceeds maximum length of {max_length} characters", field=field_name, value=value)

    # Comprehensive security validation
    # Check for potentially malicious patterns
    malicious_patterns = [
        # HTML/XML injection
        r'[<>"\']',
        # SQL injection patterns
        r"\b(union|select|insert|update|delete|drop|create|alter|exec|execute|script)\b",
        # JavaScript injection
        r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>",
        # Command injection (more specific to avoid false positives)
        r"[;&|`(){}[\]]",
        # Path traversal
        r"\.\./|\.\.\\",
        # Null bytes
        r"\x00",
        # Control characters
        r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]",
    ]

    for pattern in malicious_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            raise ValidationError(f"{field_name} contains potentially malicious content", field=field_name, value=value)

    # Check for excessive whitespace or control characters
    if value != value.strip():
        raise ValidationError(f"{field_name} cannot start or end with whitespace", field=field_name, value=value)

    # Check for non-printable characters (except common whitespace)
    if not all(ord(c) >= 32 or c in "\t\n\r" for c in value):
        raise ValidationError(f"{field_name} contains non-printable characters", field=field_name, value=value)


class PaymentType(Enum):
    """Payment types supported by the SDK."""

    PAY_PER_USE = "pay_per_use"
    SUBSCRIPTION = "subscription"
    FREEMIUM = "freemium"


class BillingPeriod(Enum):
    """Billing periods for subscriptions."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


@dataclass
class PaymentPlan:
    """Represents a payment plan that users can subscribe to."""

    id: str
    name: str
    description: Optional[str] = None
    payment_type: PaymentType | str = PaymentType.PAY_PER_USE
    price: float = 0.0
    currency: str = "USD"
    price_per_request: Optional[float] = None
    billing_period: Optional[BillingPeriod | str] = None
    requests_per_period: Optional[int] = None
    free_requests: int = 0
    features: list[str] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Convert string enums and validate the plan."""
        if isinstance(self.payment_type, str):
            try:
                self.payment_type = PaymentType(self.payment_type)
            except ValueError:
                valid_types = [pt.value for pt in PaymentType]
                raise ValidationError(
                    f"Invalid payment type: {self.payment_type}. Must be one of: {', '.join(valid_types)}",
                    field="payment_type",
                    value=self.payment_type,
                )
        if isinstance(self.billing_period, str) and self.billing_period:
            try:
                self.billing_period = BillingPeriod(self.billing_period)
            except ValueError:
                valid_periods = [bp.value for bp in BillingPeriod]
                raise ValidationError(
                    f"Invalid billing period: {self.billing_period}. Must be one of: {', '.join(valid_periods)}",
                    field="billing_period",
                    value=self.billing_period,
                )
        self.validate()
        logger.debug("Created payment plan: %s", self.name)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with proper serialization."""
        data = asdict(self)
        data["payment_type"] = self.payment_type.value if isinstance(self.payment_type, PaymentType) else str(self.payment_type)
        if self.billing_period:
            data["billing_period"] = (
                self.billing_period.value if isinstance(self.billing_period, BillingPeriod) else str(self.billing_period)
            )
        data["created_at"] = self.created_at.isoformat()
        return data

    def is_freemium(self) -> bool:
        """Check if this is a freemium plan."""
        return self.payment_type == PaymentType.FREEMIUM

    def is_subscription(self) -> bool:
        """Check if this is a subscription plan."""
        return self.payment_type == PaymentType.SUBSCRIPTION

    def is_pay_per_use(self) -> bool:
        """Check if this is a pay-per-use plan."""
        return self.payment_type == PaymentType.PAY_PER_USE

    def get_price_display(self) -> str:
        """Get formatted price string."""
        if self.is_freemium():
            return "Free"
        elif self.is_pay_per_use() and self.price_per_request:
            return f"{self.price_per_request:.2f} {self.currency} per request"
        return f"{self.price:.2f} {self.currency}"

    def validate(self) -> None:
        """Validate the payment plan fields."""
        _validate_string_field(self.id, "Plan ID", max_length=100)
        _validate_string_field(self.name, "Plan name", max_length=255)
        if self.price < 0:
            raise ValidationError("Plan price cannot be negative", field="price", value=self.price)
        if self.price_per_request is not None and self.price_per_request < 0:
            raise ValidationError("Price per request cannot be negative", field="price_per_request", value=self.price_per_request)
        # Validate currency against supported currencies
        if not self.currency or not isinstance(self.currency, str):
            raise ValidationError("Currency must be a string", field="currency", value=self.currency)
        if self.currency.upper() not in SUPPORTED_CURRENCIES:
            raise ValidationError(
                f"Currency {self.currency} is not supported. Supported currencies: {', '.join(sorted(SUPPORTED_CURRENCIES))}",
                field="currency",
                value=self.currency,
            )
        if self.features is not None and not isinstance(self.features, list):
            raise ValidationError("Features must be a list", field="features", value=self.features)
        if self.features and not all(isinstance(f, str) for f in self.features):
            raise ValidationError("All features must be strings", field="features", value=self.features)
        if self.is_subscription() and not self.billing_period:
            raise ValidationError(
                "Billing period is required for subscription plans", field="billing_period", value=self.billing_period
            )
        if self.requests_per_period is not None and self.requests_per_period < 0:
            raise ValidationError(
                "Requests per period cannot be negative", field="requests_per_period", value=self.requests_per_period
            )
        if self.free_requests < 0:
            raise ValidationError("Free requests cannot be negative", field="free_requests", value=self.free_requests)
        # Validate minimum amounts for stablecoins
        if not self.is_freemium() and self.currency.upper() in MINIMUM_AMOUNTS:
            min_amount = MINIMUM_AMOUNTS[self.currency.upper()]
            if self.price < min_amount:
                raise ValidationError(
                    f"Price {self.price} {self.currency} is below the minimum {min_amount} {self.currency}",
                    field="price",
                    value=self.price,
                )
            if self.price_per_request is not None and self.price_per_request < min_amount:
                raise ValidationError(
                    f"Price per request {self.price_per_request} {self.currency} is below the minimum {min_amount} {self.currency}",
                    field="price_per_request",
                    value=self.price_per_request,
                )
        if self.description is not None:
            _validate_string_field(self.description, "Description", max_length=1000)


@dataclass
class Subscription:
    """Represents a user's subscription to a payment plan."""

    id: str
    user_id: str
    plan_id: str
    status: str = "active"
    start_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_date: Optional[datetime] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    usage_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    # Allowed status transitions
    _ALLOWED_TRANSITIONS = {
        "active": {"cancelled", "expired", "suspended"},
        "cancelled": {"active"},
        "expired": {"active"},
        "suspended": {"active", "cancelled"},
    }

    def __post_init__(self) -> None:
        """Validate the subscription after initialization."""
        self.validate()
        logger.debug("Created subscription for plan %s", self.plan_id)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with proper datetime serialization."""
        data = asdict(self)

        # Validate and serialize start_date
        if isinstance(self.start_date, str):
            try:
                datetime.fromisoformat(self.start_date)
            except ValueError:
                raise ValidationError(
                    f"Invalid ISO 8601 datetime format for start_date: {self.start_date}",
                    field="start_date",
                    value=self.start_date,
                )
        data["start_date"] = self.start_date.isoformat() if isinstance(self.start_date, datetime) else str(self.start_date)

        # Validate and serialize end_date
        if self.end_date:
            if isinstance(self.end_date, str):
                try:
                    datetime.fromisoformat(self.end_date)
                except ValueError:
                    raise ValidationError(
                        f"Invalid ISO 8601 datetime format for end_date: {self.end_date}", field="end_date", value=self.end_date
                    )
            data["end_date"] = self.end_date.isoformat() if isinstance(self.end_date, datetime) else str(self.end_date)

        # Validate and serialize current_period_start
        if self.current_period_start:
            if isinstance(self.current_period_start, str):
                try:
                    datetime.fromisoformat(self.current_period_start)
                except ValueError:
                    raise ValidationError(
                        f"Invalid ISO 8601 datetime format for current_period_start: {self.current_period_start}",
                        field="current_period_start",
                        value=self.current_period_start,
                    )
            data["current_period_start"] = (
                self.current_period_start.isoformat()
                if isinstance(self.current_period_start, datetime)
                else str(self.current_period_start)
            )

        # Validate and serialize current_period_end
        if self.current_period_end:
            if isinstance(self.current_period_end, str):
                try:
                    datetime.fromisoformat(self.current_period_end)
                except ValueError:
                    raise ValidationError(
                        f"Invalid ISO 8601 datetime format for current_period_end: {self.current_period_end}",
                        field="current_period_end",
                        value=self.current_period_end,
                    )
            data["current_period_end"] = (
                self.current_period_end.isoformat()
                if isinstance(self.current_period_end, datetime)
                else str(self.current_period_end)
            )
        return data

    def is_active(self) -> bool:
        """Check if the subscription is currently active."""
        if self.status != "active":
            return False
        now = datetime.now(timezone.utc)
        if self.end_date:
            end_date = self.end_date
            if isinstance(end_date, str):
                try:
                    end_date = datetime.fromisoformat(end_date)
                except Exception:
                    return False
            if now > end_date:
                return False
        if self.current_period_end:
            period_end = self.current_period_end
            if isinstance(period_end, str):
                try:
                    period_end = datetime.fromisoformat(period_end)
                except Exception:
                    return False
            if now > period_end:
                return False
        return True

    def is_expired(self) -> bool:
        """Check if the subscription has expired."""
        return not self.is_active()

    def get_days_remaining(self) -> Optional[int]:
        """Get days remaining in current billing period."""
        if not self.current_period_end:
            return None
        end_date = self.current_period_end
        if isinstance(end_date, str):
            try:
                end_date = datetime.fromisoformat(end_date)
            except Exception:
                return None
        now = datetime.now(timezone.utc)
        if now > end_date:
            return 0
        return (end_date - now).days

    def set_status(self, new_status: str) -> None:
        """Set subscription status with transition validation."""
        # Allow setting the same status (no-op)
        if new_status == self.status:
            logger.debug(sanitize_log_message(f"Subscription status already {new_status}, no change needed"))
            return

        if new_status not in self._ALLOWED_TRANSITIONS.get(self.status, set()):
            raise ValidationError(
                f"Cannot change subscription status from {self.status} to {new_status}", field="status", value=new_status
            )
        self.status = new_status
        logger.debug(sanitize_log_message(f"Changed subscription status to: {new_status}"))

    def increment_usage(self) -> None:
        """Increment the usage count."""
        self.usage_count += 1
        logger.debug(sanitize_log_message("Incremented usage count for subscription"))

    def validate(self) -> None:
        """Validate the subscription fields."""
        _validate_string_field(self.id, "Subscription ID", max_length=100)
        _validate_string_field(self.user_id, "User ID", max_length=100)
        _validate_string_field(self.plan_id, "Plan ID", max_length=100)
        valid_statuses = ("active", "cancelled", "expired", "suspended")
        if self.status not in valid_statuses:
            raise ValidationError(
                f"Invalid subscription status. Must be one of: {valid_statuses}", field="status", value=self.status
            )
        # Note: Status transition validation is handled by set_status() method
        # This validate() method only checks that the status is valid, not the transition
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError("End date cannot be before start date", field="end_date", value=self.end_date)
        if self.current_period_end and self.current_period_start and self.current_period_end < self.current_period_start:
            raise ValidationError(
                "Current period end cannot be before current period start",
                field="current_period_end",
                value=self.current_period_end,
            )
        if self.usage_count < 0:
            raise ValidationError("Usage count cannot be negative", field="usage_count", value=self.usage_count)
        if not isinstance(self.metadata, dict):
            raise ValidationError("Metadata must be a dictionary", field="metadata", value=self.metadata)
        _validate_json_serializable(self.metadata, "metadata")


@dataclass
class UsageRecord:
    """Represents a single usage event for a user and feature."""

    id: str
    user_id: str
    feature: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    cost: Optional[float] = None
    currency: str = "USD"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the usage record after initialization."""
        self.validate()
        logger.debug(sanitize_log_message("Created usage record"))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with proper datetime serialization."""
        data = asdict(self)

        # Validate and serialize timestamp
        if isinstance(self.timestamp, str):
            try:
                datetime.fromisoformat(self.timestamp)
            except ValueError:
                raise ValidationError(
                    f"Invalid ISO 8601 datetime format for timestamp: {self.timestamp}", field="timestamp", value=self.timestamp
                )
        data["timestamp"] = self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp)
        return data

    def get_cost_display(self) -> str:
        """Get formatted cost string."""
        if self.cost is None:
            return "Free"
        return f"{self.cost:.2f} {self.currency}"

    def is_free(self) -> bool:
        """Check if this usage was free."""
        return self.cost is None or self.cost == 0.0

    def validate(self) -> None:
        """Validate the usage record fields."""
        _validate_string_field(self.id, "UsageRecord ID", max_length=100)
        _validate_string_field(self.user_id, "User ID", max_length=100)
        _validate_string_field(self.feature, "Feature", max_length=255)
        if self.cost is not None and self.cost < 0:
            raise ValidationError("Cost cannot be negative", field="cost", value=self.cost)
        # Validate minimum amounts for stablecoins
        if self.currency.upper() in MINIMUM_AMOUNTS and self.cost is not None:
            min_amount = MINIMUM_AMOUNTS[self.currency.upper()]
            if self.cost < min_amount:
                raise ValidationError(
                    f"Cost {self.cost} {self.currency} is below the minimum {min_amount} {self.currency}",
                    field="cost",
                    value=self.cost,
                )
        # Validate currency against supported currencies
        if not self.currency or not isinstance(self.currency, str):
            raise ValidationError("Currency must be a string", field="currency", value=self.currency)
        if self.currency.upper() not in SUPPORTED_CURRENCIES:
            raise ValidationError(
                f"Currency {self.currency} is not supported. Supported currencies: {', '.join(sorted(SUPPORTED_CURRENCIES))}",
                field="currency",
                value=self.currency,
            )
        if not isinstance(self.metadata, dict):
            raise ValidationError("Metadata must be a dictionary", field="metadata", value=self.metadata)
        _validate_json_serializable(self.metadata, "metadata")


@dataclass
class PaymentTransaction:
    """Represents a payment transaction processed through a payment provider."""

    id: str
    user_id: str
    amount: float
    currency: str = "USD"
    payment_method: str = "unknown"
    status: str = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the transaction after initialization."""
        self.validate()
        logger.debug("Created payment transaction")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with proper datetime serialization."""
        data = asdict(self)

        # Validate and serialize created_at
        if isinstance(self.created_at, str):
            try:
                datetime.fromisoformat(self.created_at)
            except ValueError:
                raise ValidationError(
                    f"Invalid ISO 8601 datetime format for created_at: {self.created_at}",
                    field="created_at",
                    value=self.created_at,
                )
        data["created_at"] = self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at)

        # Validate and serialize completed_at
        if self.completed_at:
            if isinstance(self.completed_at, str):
                try:
                    datetime.fromisoformat(self.completed_at)
                except ValueError:
                    raise ValidationError(
                        f"Invalid ISO 8601 datetime format for completed_at: {self.completed_at}",
                        field="completed_at",
                        value=self.completed_at,
                    )
            data["completed_at"] = (
                self.completed_at.isoformat() if isinstance(self.completed_at, datetime) else str(self.completed_at)
            )
        return data

    def is_completed(self) -> bool:
        """Check if the transaction is completed."""
        return self.status == "completed"

    def is_failed(self) -> bool:
        """Check if the transaction failed."""
        return self.status == "failed"

    def is_pending(self) -> bool:
        """Check if the transaction is pending."""
        return self.status == "pending"

    def is_refunded(self) -> bool:
        """Check if the transaction was refunded."""
        return self.status == "refunded"

    def mark_completed(self) -> None:
        """Mark the transaction as completed."""
        if self.status not in ["pending"]:
            raise ValidationError(
                f"Cannot mark transaction as completed from status '{self.status}'. Only 'pending' transactions can be completed.",
                field="status",
                value=self.status,
            )
        self.status = "completed"
        self.completed_at = datetime.now(timezone.utc)
        logger.info("Marked transaction as completed")

    def mark_failed(self) -> None:
        """Mark the transaction as failed."""
        if self.status not in ["pending", "completed"]:
            raise ValidationError(
                f"Cannot mark transaction as failed from status '{self.status}'. Only 'pending' or 'completed' transactions can be failed.",
                field="status",
                value=self.status,
            )
        self.status = "failed"
        logger.warning("Marked transaction as failed")

    def mark_refunded(self) -> None:
        """Mark the transaction as refunded."""
        if self.status not in ["completed"]:
            raise ValidationError(
                f"Cannot mark transaction as refunded from status '{self.status}'. Only 'completed' transactions can be refunded.",
                field="status",
                value=self.status,
            )
        self.status = "refunded"
        logger.info("Marked transaction as refunded")

    def get_amount_display(self) -> str:
        """Get formatted amount string."""
        return f"{self.amount:.2f} {self.currency}"

    def get_processing_time(self) -> Optional[float]:
        """Get processing time in seconds."""
        if not self.completed_at:
            return None
        return (self.completed_at - self.created_at).total_seconds()

    def validate(self) -> None:
        """Validate the payment transaction fields."""
        _validate_string_field(self.id, "Transaction ID", max_length=100)
        _validate_string_field(self.user_id, "User ID", max_length=100)
        if not isinstance(self.amount, (int, float)) or self.amount < 0:
            raise ValidationError("Amount must be a non-negative number", field="amount", value=self.amount)
        # Validate currency against supported currencies
        if not self.currency or not isinstance(self.currency, str):
            raise ValidationError("Currency must be a string", field="currency", value=self.currency)
        if self.currency.upper() not in SUPPORTED_CURRENCIES:
            raise ValidationError(
                f"Currency {self.currency} is not supported. Supported currencies: {', '.join(sorted(SUPPORTED_CURRENCIES))}",
                field="currency",
                value=self.currency,
            )
        _validate_string_field(self.payment_method, "Payment method", max_length=100)
        valid_statuses = ("pending", "completed", "failed", "refunded", "cancelled")
        if self.status not in valid_statuses:
            raise ValidationError(
                f"Invalid transaction status. Must be one of: {valid_statuses}", field="status", value=self.status
            )
        if self.completed_at and self.completed_at < self.created_at:
            raise ValidationError("Completed date cannot be before created date", field="completed_at", value=self.completed_at)
        if not isinstance(self.metadata, dict):
            raise ValidationError("Metadata must be a dictionary", field="metadata", value=self.metadata)
        # Validate minimum amounts for stablecoins
        if self.currency.upper() in MINIMUM_AMOUNTS:
            min_amount = MINIMUM_AMOUNTS[self.currency.upper()]
            if self.amount < min_amount:
                raise ValidationError(
                    f"Amount {self.amount} {self.currency} is below the minimum {min_amount} {self.currency}",
                    field="amount",
                    value=self.amount,
                )
