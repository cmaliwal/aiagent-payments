# Stripe Deep Dive

A comprehensive guide to integrating Stripe payments with AIAgent Payments, covering all features, best practices, and advanced configurations.

## 🎯 Overview

Stripe is the most popular and feature-rich payment provider supported by AIAgent Payments. This guide covers everything from basic setup to advanced features like subscriptions, webhooks, and customer management.

## 🚀 Quick Start

### Basic Setup

```python
from aiagent_payments import PaymentProcessor

# Initialize Stripe processor
processor = PaymentProcessor(
    provider="stripe",
    api_key="sk_test_your_stripe_secret_key"
)

# Process a simple payment
result = processor.process_payment(
    amount=1000,  # $10.00 in cents
    currency="usd",
    description="AI Agent Consultation"
)
```

### Environment Configuration

```bash
# Required environment variables
export STRIPE_SECRET_KEY="sk_test_..."
export STRIPE_PUBLISHABLE_KEY="pk_test_..."

# Optional: Webhook secret
export STRIPE_WEBHOOK_SECRET="whsec_..."
```

## 💳 Payment Methods

### Payment Intents (Recommended)

```python
# Create a payment intent
result = processor.process_payment(
    amount=1000,
    currency="usd",
    description="AI Agent Service",
    payment_method_types=["card", "us_bank_account"],
    capture_method="automatic",  # or "manual"
    confirm=True
)

print(f"Payment Intent ID: {result.payment_id}")
print(f"Status: {result.status}")
print(f"Client Secret: {result.client_secret}")
```

### Checkout Sessions

```python
# Create a checkout session
checkout_result = processor.create_checkout_session(
    user_id="user@example.com",
    plan=payment_plan,  # PaymentPlan object
    success_url="https://yourapp.com/success",
    cancel_url="https://yourapp.com/cancel",
    metadata={"source": "web_checkout"}
)

print(f"Checkout URL: {checkout_result['url']}")
print(f"Session ID: {checkout_result['session_id']}")
```

### Stablecoin Checkout Sessions

```python
# Create a stablecoin checkout session
session = processor.create_stablecoin_checkout_session(
    amount=1000,
    currency="usd",
    description="AI Agent Service (USDC)",
    success_url="https://yourapp.com/success",
    cancel_url="https://yourapp.com/cancel",
    stablecoins=["usdc", "usdt"]
)

print(f"Stablecoin Checkout URL: {session.url}")
```

## 👥 Customer Management

### Create Customer

```python
# Create a new customer
customer = processor.create_customer(
    email="user@example.com",
    name="John Doe",
    metadata={
        "ai_agent_user_id": "user_123",
        "subscription_tier": "pro"
    }
)

print(f"Customer ID: {customer.customer_id}")
```

### Retrieve Customer

```python
# Get customer details
customer = processor.get_customer("cus_1234567890")

print(f"Email: {customer.email}")
print(f"Name: {customer.name}")
print(f"Created: {customer.created}")
```

### Update Customer

```python
# Update customer information
updated_customer = processor.update_customer(
    customer_id="cus_1234567890",
    email="newemail@example.com",
    name="John Smith",
    metadata={"last_payment": "2024-01-15"}
)
```

### List Customers

```python
# Get all customers
customers = processor.list_customers(limit=10)

for customer in customers:
    print(f"ID: {customer.customer_id}")
    print(f"Email: {customer.email}")
    print(f"Name: {customer.name}")
    print("---")
```

## 🔄 Subscription Management

**Important Note:** This SDK manages subscriptions internally, not through Stripe's subscription system. Stripe is used for one-time payments, while the SDK handles subscription logic, billing periods, and access control.

### Create Internal Subscription

```python
from aiagent_payments import PaymentManager

# After successful payment, create subscription in SDK
payment_manager = PaymentManager(storage=storage, payment_provider=stripe_provider)

# Create subscription (manages billing periods, access control internally)
subscription = payment_manager.subscribe_user(
    user_id="user@example.com",
    plan_id="pro_plan",
    metadata={"payment_intent_id": "pi_1234567890"}
)

print(f"Subscription ID: {subscription.id}")
print(f"Status: {subscription.status}")
print(f"Billing Period: {subscription.current_period_end}")
```

### Manage Subscriptions

```python
# Cancel subscription
cancelled = payment_manager.cancel_user_subscription("user@example.com")

# Get user subscription
subscription = payment_manager.get_user_subscription("user@example.com")

# Check subscription access
has_access = payment_manager.check_access("user@example.com", "premium_feature")
```

### Subscription Features

- **Internal Billing Management**: SDK handles billing periods, renewals, and access control
- **Flexible Plans**: Support for daily, weekly, monthly, yearly billing cycles
- **Usage Tracking**: Automatic usage counting and limit enforcement
- **Access Control**: Decorator-based feature access control
- **No Stripe Dashboard Management**: No need to create Stripe products/prices for each plan

## 🔗 Webhooks

### Webhook Setup

```python
from flask import Flask, request

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    # Verify webhook signature
    try:
        event = processor.verify_webhook(
            payload=request.data,
            signature=request.headers.get('Stripe-Signature')
        )
    except Exception as e:
        return {'error': 'Invalid signature'}, 400
    
    # Handle different event types
    if event.type == 'payment_intent.succeeded':
        handle_successful_payment(event.data)
    elif event.type == 'payment_intent.payment_failed':
        handle_failed_payment(event.data)
    elif event.type == 'invoice.payment_succeeded':
        handle_successful_invoice(event.data)
    elif event.type == 'invoice.payment_failed':
        handle_failed_invoice(event.data)
    
    return {'status': 'success'}, 200

def handle_successful_payment(data):
    payment_intent = data.object
    print(f"Payment succeeded: {payment_intent.id}")
    # Grant access to AI agent features

def handle_failed_payment(data):
    payment_intent = data.object
    print(f"Payment failed: {payment_intent.id}")
    # Handle payment failure
```

### Webhook Events

Common webhook events to handle:

| Event Type | Description | Action |
|------------|-------------|--------|
| `payment_intent.succeeded` | Payment completed successfully | Grant access, create internal subscription |
| `payment_intent.payment_failed` | Payment failed | Notify user, retry logic |
| `charge.refunded` | Payment refunded | Update transaction status |
| `customer.created` | New customer created | Store customer information |
| `customer.updated` | Customer information updated | Update customer records |

## 💰 Pricing and Plans

### Create Price

```python
# Create a recurring price
price = processor.create_price(
    unit_amount=2000,  # $20.00
    currency="usd",
    recurring={
        "interval": "month",
        "interval_count": 1
    },
    product_data={
        "name": "Pro AI Agent Plan",
        "description": "Unlimited AI agent access"
    }
)

print(f"Price ID: {price.price_id}")
```

### Create Product

```python
# Create a product
product = processor.create_product(
    name="AI Agent Pro",
    description="Professional AI agent access",
    metadata={
        "features": "unlimited_requests,priority_support",
        "tier": "pro"
    }
)

print(f"Product ID: {product.product_id}")
```

## 🔐 Security Best Practices

### API Key Management

```python
import os

# Use environment variables
processor = PaymentProcessor(
    provider="stripe",
    api_key=os.getenv("STRIPE_SECRET_KEY")
)

# Never hardcode keys
# ❌ Bad
processor = PaymentProcessor(api_key="sk_test_123...")

# ✅ Good
processor = PaymentProcessor(api_key=os.getenv("STRIPE_SECRET_KEY"))
```

### Webhook Security

```python
# Always verify webhook signatures
@app.route('/webhook', methods=['POST'])
def handle_webhook():
    signature = request.headers.get('Stripe-Signature')
    
    if not signature:
        return {'error': 'No signature'}, 400
    
    try:
        event = processor.verify_webhook(request.data, signature)
    except Exception as e:
        return {'error': 'Invalid signature'}, 400
    
    # Process the event
    return {'status': 'success'}, 200
```

### Idempotency Keys

```python
import uuid

# Use idempotency keys for critical operations
idempotency_key = str(uuid.uuid4())

result = processor.process_payment(
    amount=1000,
    currency="usd",
    description="AI Agent Service",
    idempotency_key=idempotency_key
)
```

## 📊 Analytics and Reporting

### Payment Analytics

```python
# Get payment statistics
stats = processor.get_payment_statistics(
    start_date="2024-01-01",
    end_date="2024-01-31"
)

print(f"Total payments: {stats.total_payments}")
print(f"Total amount: ${stats.total_amount / 100:.2f}")
print(f"Success rate: {stats.success_rate:.2%}")
```

### Customer Analytics

```python
# Get customer insights
insights = processor.get_customer_insights()

print(f"Total customers: {insights.total_customers}")
print(f"Active subscriptions: {insights.active_subscriptions}")
print(f"Average revenue per customer: ${insights.avg_revenue:.2f}")
```

## 🧪 Testing

### Test Cards

```python
# Test successful payment
result = processor.process_payment(
    amount=1000,
    currency="usd",
    payment_method="pm_card_visa"  # Stripe test card
)

# Test declined payment
result = processor.process_payment(
    amount=1000,
    currency="usd",
    payment_method="pm_card_chargeDeclined"
)

# Test 3D Secure
result = processor.process_payment(
    amount=1000,
    currency="usd",
    payment_method="pm_card_visa_debit"
)
```

### Test Scenarios

```python
# Test different currencies
currencies = ["usd", "eur", "gbp", "jpy"]
for currency in currencies:
    result = processor.process_payment(
        amount=1000,
        currency=currency,
        description=f"Test payment in {currency.upper()}"
    )
    print(f"{currency.upper()}: {result.status}")

# Test different amounts
amounts = [100, 500, 1000, 5000, 10000]
for amount in amounts:
    result = processor.process_payment(
        amount=amount,
        currency="usd",
        description=f"Test payment of ${amount/100:.2f}"
    )
    print(f"${amount/100:.2f}: {result.status}")
```

## 🚨 Error Handling

### Common Errors

```python
from aiagent_payments.exceptions import PaymentError, StripeError

try:
    result = processor.process_payment(
        amount=1000,
        currency="usd",
        description="Test payment"
    )
except StripeError as e:
    if "card_declined" in str(e):
        print("Card was declined")
    elif "insufficient_funds" in str(e):
        print("Insufficient funds")
    elif "expired_card" in str(e):
        print("Card has expired")
    else:
        print(f"Stripe error: {e}")
except PaymentError as e:
    print(f"Payment error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Error Recovery

```python
import time

def process_payment_with_retry(amount, currency, description, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = processor.process_payment(
                amount=amount,
                currency=currency,
                description=description
            )
            return result
        except StripeError as e:
            if "rate_limit" in str(e) and attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                raise e
```

## 🔧 Advanced Configuration

### Custom Headers

```python
# Add custom headers for API calls
processor = PaymentProcessor(
    provider="stripe",
    api_key="sk_test_...",
    headers={
        "Stripe-Version": "2023-10-16",
        "User-Agent": "AIAgentPayments/1.0"
    }
)
```

### Proxy Configuration

```python
# Configure proxy for API calls
processor = PaymentProcessor(
    provider="stripe",
    api_key="sk_test_...",
    proxy={
        "http": "http://proxy.example.com:8080",
        "https": "https://proxy.example.com:8080"
    }
)
```

### Timeout Configuration

```python
# Set custom timeouts
processor = PaymentProcessor(
    provider="stripe",
    api_key="sk_test_...",
    timeout=30  # 30 seconds
)
```

## 📱 Mobile Integration

### React Native

```javascript
// React Native with Stripe
import { initStripe, createToken } from '@stripe/stripe-react-native';

// Initialize Stripe
await initStripe({
  publishableKey: 'pk_test_...',
});

// Create payment token
const token = await createToken({
  type: 'Card',
  card: {
    number: '4242424242424242',
    expMonth: 12,
    expYear: 2025,
    cvc: '123',
  },
});

// Send token to your backend
const response = await fetch('/api/payment', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    token: token.tokenId,
    amount: 1000,
    currency: 'usd',
  }),
});
```

### Flutter

```dart
// Flutter with Stripe
import 'package:stripe_payment/stripe_payment.dart';

// Initialize Stripe
StripePayment.setOptions(StripeOptions(
  publishableKey: "pk_test_...",
  merchantId: "merchant.com.yourapp",
  androidPayMode: 'test',
));

// Create payment method
PaymentMethod paymentMethod = await StripePayment.createPaymentMethod(
  PaymentMethodRequest(
    card: CreditCard(
      number: "4242424242424242",
      expMonth: 12,
      expYear: 2025,
      cvc: "123",
    ),
  ),
);

// Send to backend
final response = await http.post(
  Uri.parse('/api/payment'),
  headers: {'Content-Type': 'application/json'},
  body: json.encode({
    'payment_method_id': paymentMethod.id,
    'amount': 1000,
    'currency': 'usd',
  }),
);
```

## 🔄 Migration Guide

### From Direct Stripe Integration

```python
# Old direct Stripe code
import stripe
stripe.api_key = "sk_test_..."

payment_intent = stripe.PaymentIntent.create(
    amount=1000,
    currency="usd",
    description="AI Agent Service"
)

# New AIAgent Payments code
from aiagent_payments import PaymentProcessor

processor = PaymentProcessor(provider="stripe", api_key="sk_test_...")

result = processor.process_payment(
    amount=1000,
    currency="usd",
    description="AI Agent Service"
)
```

### From Other Payment Providers

```python
# Migrate from PayPal
paypal_processor = PaymentProcessor(provider="paypal")
stripe_processor = PaymentProcessor(provider="stripe")

# Migrate customer data
customers = paypal_processor.list_customers()
for customer in customers:
    stripe_customer = stripe_processor.create_customer(
        email=customer.email,
        name=customer.name,
        metadata={"migrated_from": "paypal"}
    )
```

## 📚 Additional Resources

### Stripe Documentation
- [Stripe API Reference](https://stripe.com/docs/api)
- [Stripe Webhooks](https://stripe.com/docs/webhooks)
- [Stripe Testing](https://stripe.com/docs/testing)

### AIAgent Payments Examples
- [Basic Usage Examples](https://github.com/cmaliwal/aiagent-payments/tree/main/examples/basic)
- [Advanced Features](https://github.com/cmaliwal/aiagent-payments/tree/main/examples/advanced)
- [Webhook Handling](https://github.com/cmaliwal/aiagent-payments/tree/main/examples/real_world)

### Community Support
- [GitHub Issues](https://github.com/cmaliwal/aiagent-payments/issues)
- [Discussions](https://github.com/cmaliwal/aiagent-payments/discussions)
- [Stripe Community](https://support.stripe.com/)

---

**Ready to integrate Stripe?** Start with the [Getting Started](Getting-Started) guide and then dive into the specific features you need! 

## 🧪 Fallback & Mock Mode

**Automatic Fallback:**  
If the `stripe` library is not installed in your environment, the Stripe provider will automatically switch to "mock mode" in development and test environments. In this mode:
- All payment, refund, and status operations return simulated/mock results.
- No real API calls are made to Stripe.
- This is ideal for local development, CI pipelines, and testing without real credentials.

**How it works:**
```python
# If stripe is missing, fallback is automatic in dev/test:
try:
    import stripe
except ImportError:
    print("stripe not installed: Stripe provider will use mock mode.")

from aiagent_payments.providers import StripeProvider
stripe_provider = StripeProvider(api_key="any_value")

# All methods will return mock results in dev/test:
transaction = stripe_provider.process_payment(
    user_id="test_user",
    amount=10.0,
    currency="USD"
)
print(transaction.status)  # "completed" (mock)
print(transaction.metadata["mock_transaction"])  # True
```

**Tip:**  
You can deliberately test fallback mode by uninstalling `stripe` in a virtual environment:
```bash
pip uninstall stripe
```
Or by using a minimal Docker/CI image.

**Note:**
- A warning will be logged when fallback is activated.
- For more on simulated/test payments, see the [Mock Provider Guide](Mock-Provider-Guide.md). 