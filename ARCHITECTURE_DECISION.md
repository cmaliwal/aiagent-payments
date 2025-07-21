# Architecture Decision: Payment Integration vs Usage Tracking

## Overview

The `aiagent-payments` SDK supports two different usage patterns, allowing developers to choose the approach that best fits their needs.

## Two Usage Patterns

### Pattern 1: Complete Payment Gateway
The SDK handles all payment processing, including:
- Payment collection
- Provider integration (Stripe, PayPal, Crypto)
- Transaction management
- Billing and invoicing

```python
from aiagent_payments import PaymentManager

# Initialize with payment provider
pm = PaymentManager(
    payment_provider=StripeProvider(api_key="sk_test_...")
)

# Process payment through SDK
transaction = pm.process_payment("user1", 10.0, "USD")

# Check access (payment already handled)
if pm.check_access("user1", "ai_feature"):
    # Allow access
```

### Pattern 2: Usage Tracking Only
The SDK only handles usage tracking and access control:
- Usage recording
- Access validation
- Billing calculations
- No payment processing

```python
from aiagent_payments import PaymentManager

# Initialize without payment provider
pm = PaymentManager()

# User handles their own payments
# ... user's payment processing ...

# Record usage and check access
pm.record_usage("user1", "ai_feature", 0.5)
if pm.check_access("user1", "ai_feature"):
    # Allow access
```

## When to Use Each Pattern

### Use Complete Payment Gateway When:
- Building a new application from scratch
- Want "batteries included" solution
- Don't have existing payment infrastructure
- Need quick setup and deployment
- Want built-in crypto support

### Use Usage Tracking Only When:
- Have existing payment infrastructure
- Want to maintain payment control
- Building on top of existing systems
- Need custom payment flows
- Want to minimize SDK dependencies

## Implementation Details

### Core Components (Always Available)
- `PaymentManager`: Main interface
- `UsageTracker`: Usage recording and analysis
- `SubscriptionManager`: Subscription lifecycle
- `StorageBackend`: Data persistence
- `Models`: Data structures

### Optional Components
- `PaymentProvider`: Payment processing
- `CryptoProvider`: Cryptocurrency support
- `StripeProvider`: Stripe integration
- `PayPalProvider`: PayPal integration

## Configuration Examples

### Minimal Setup (Usage Tracking Only)
```python
from aiagent_payments import PaymentManager, MemoryStorage

# No payment provider needed
pm = PaymentManager(storage=MemoryStorage())

# Just track usage
pm.record_usage("user1", "feature", 0.1)
pm.check_access("user1", "feature")
```

### Full Setup (Payment Gateway)
```python
from aiagent_payments import PaymentManager, StripeProvider, FileStorage

# With payment provider
pm = PaymentManager(
    storage=FileStorage("data"),
    payment_provider=StripeProvider(api_key="sk_test_...")
)
```

## Security Considerations

### Payment Gateway Mode
- SDK handles sensitive payment data
- Requires secure API key management
- Payment provider security best practices

### Usage Tracking Mode
- No sensitive payment data in SDK
- User controls their own security
- Simpler security model

## Recommended Approach

### For New Projects
Start with **Payment Gateway** mode for quick setup.

### For Existing Projects
Use **Usage Tracking** mode and integrate with existing payment systems.

### For Enterprise
Consider **Usage Tracking** mode for better control and integration.

## Future Enhancements

### Planned Features
- Webhook support for payment events
- More payment providers (Square, Adyen, etc.)
- Advanced crypto features
- Subscription webhooks
- Usage analytics dashboard

### Customization Options
- Custom payment provider implementations
- Flexible billing models
- Custom storage backends
- Plugin architecture for extensions 