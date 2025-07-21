"""
AI Agent Payments SDK

Provides payment, subscription, and usage tracking for AI/autonomous agents.
"""

from . import config, exceptions, models, storage, utils
from .core import PaymentManager, SubscriptionManager, UsageTracker
from .exceptions import PaymentRequired, UsageLimitExceeded
from .models import BillingPeriod, PaymentPlan, PaymentType
from .providers import PaymentProvider, create_payment_provider
from .providers.mock import MockProvider
from .storage.memory import MemoryStorage

__version__ = "0.0.1-beta"

__all__ = [
    "PaymentManager",
    "SubscriptionManager",
    "UsageTracker",
    "PaymentProvider",
    "create_payment_provider",
    "models",
    "exceptions",
    "storage",
    "utils",
    "config",
    "PaymentPlan",
    "BillingPeriod",
    "PaymentType",
    "UsageLimitExceeded",
    "PaymentRequired",
    "MemoryStorage",
    "MockProvider",
]
