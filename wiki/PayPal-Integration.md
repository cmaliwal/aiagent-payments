# PayPal Integration Guide

A comprehensive guide to integrating PayPal payments with AIAgent Payments, covering Express Checkout, subscriptions, webhooks, and advanced features.

## 🎯 Overview

PayPal is one of the most trusted payment providers globally, offering Express Checkout, subscriptions, and support for multiple currencies. This guide covers everything from basic setup to advanced PayPal features.

## 🚀 Quick Start

### Basic Setup

```python
from aiagent_payments.providers import create_payment_provider
from aiagent_payments.storage import MemoryStorage

# Initialize PayPal provider using the factory function
paypal_provider = create_payment_provider(
    "paypal",
    client_id="your_paypal_client_id",
    client_secret="your_paypal_client_secret",
    sandbox=True,  # Use sandbox for testing
    return_url="https://yourapp.com/success",
    cancel_url="https://yourapp.com/cancel",
    webhook_id="your_webhook_id"  # Optional
)

# Process a simple payment
transaction = paypal_provider.process_payment(
    user_id="user_123",
    amount=25.99,
    currency="USD",
    metadata={"service": "ai_consultation"}
)
```

### Environment Configuration

```bash
# Required environment variables
export PAYPAL_CLIENT_ID="your_paypal_client_id"
export PAYPAL_CLIENT_SECRET="your_paypal_client_secret"

# Optional environment variables
export PAYPAL_WEBHOOK_ID="your_webhook_id"
export PAYPAL_RETURN_URL="https://yourapp.com/success"
export PAYPAL_CANCEL_URL="https://yourapp.com/cancel"
```

### Direct Provider Initialization (Alternative)

```python
from aiagent_payments.providers import PayPalProvider

# Initialize PayPal provider directly
paypal_provider = PayPalProvider(
    client_id="your_paypal_client_id",
    client_secret="your_paypal_client_secret",
    sandbox=True,  # Use sandbox for testing
    storage=MemoryStorage(),
    webhook_id="your_webhook_id",  # Optional
    return_url="https://yourapp.com/success",  # Optional
    cancel_url="https://yourapp.com/cancel"  # Optional
)
```

## 🔧 Configuration Parameters

### Required Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `client_id` | str | Your PayPal application client ID | `""` |
| `client_secret` | str | Your PayPal application client secret | `""` |

### Optional Parameters

| Parameter | Type | Default | Description | Example |
|-----------|------|---------|-------------|---------|
| `sandbox` | bool | `True` | Use PayPal sandbox environment | `True` for testing, `False` for production |
| `return_url` | str | `None` | URL to redirect after successful payment | `"https://yourapp.com/success"` |
| `cancel_url` | str | `None` | URL to redirect after cancelled payment | `"https://yourapp.com/cancel"` |
| `webhook_id` | str | `None` | PayPal webhook ID for event notifications | `"webhook_123456"` |
| `timeout` | int | `30` | Request timeout in seconds | `60` |

### Factory Function vs Direct Initialization

**Factory Function (Recommended):**
```python
# Use the factory function for consistent configuration
provider = create_payment_provider(
    "paypal",
    client_id="your_client_id",
    client_secret="your_client_secret",
    return_url="https://yourapp.com/success",
    cancel_url="https://yourapp.com/cancel"
)
```

**Direct Initialization:**
```python
# Direct initialization for advanced customization
provider = PayPalProvider(
    client_id="your_client_id",
    client_secret="your_client_secret",
    return_url="https://yourapp.com/success",
    cancel_url="https://yourapp.com/cancel"
)
```

## 💳 Payment Methods

### Two-Step Payment Flow (Recommended)

```python
# Step 1: Create order
order_response = paypal_provider.create_order(
    user_id="user_123",
    amount=25.99,
    currency="USD",
    return_url="https://yourapp.com/success",
    cancel_url="https://yourapp.com/cancel",
    metadata={"service": "ai_consultation"}
)

print(f"Order ID: {order_response['id']}")
print(f"Status: {order_response['status']}")

# Extract approval link
approval_link = None
for link in order_response.get("links", []):
    if link.get("rel") == "approve":
        approval_link = link.get("href")
        break

if approval_link:
    print(f"Approval Link: {approval_link}")
    # Redirect user to approval_link

# Step 2: Capture order (after user approval)
transaction = paypal_provider.capture_order(
    user_id="user_123",
    order_id=order_response["id"],
    metadata={"captured_by": "webhook_handler"}
)

print(f"Transaction ID: {transaction.id}")
print(f"Status: {transaction.status}")
print(f"Amount: ${transaction.amount} {transaction.currency}")
```

### Direct Payment (Development Only)

```python
# WARNING: This method creates an order and immediately attempts to capture it.
# This will only work in development/testing environments or with special PayPal
# approval for reference transactions.

transaction = paypal_provider.process_payment(
    user_id="user_123",
    amount=25.99,
    currency="USD",
    metadata={"service": "ai_consultation"}
)

print(f"Transaction ID: {transaction.id}")
print(f"Status: {transaction.status}")
```

## 🔄 Webhooks

### Webhook Setup

```python
from flask import Flask, request

app = Flask(__name__)

@app.route('/webhook/paypal', methods=['POST'])
def handle_paypal_webhook():
    # Verify webhook signature
    try:
        is_valid = paypal_provider.verify_webhook_signature(
            payload=request.data.decode('utf-8'),
            headers=dict(request.headers)
        )
        if not is_valid:
            return {'error': 'Invalid signature'}, 400
    except Exception as e:
        return {'error': 'Webhook verification failed'}, 400
    
    # Parse webhook event
    event_data = request.get_json()
    event_type = event_data.get('event_type')
    
    # Handle different event types
    if event_type == 'CHECKOUT.ORDER.APPROVED':
        handle_order_approved(event_data)
    elif event_type == 'PAYMENT.CAPTURE.COMPLETED':
        handle_payment_completed(event_data)
    elif event_type == 'PAYMENT.CAPTURE.DENIED':
        handle_payment_denied(event_data)
    
    return {'status': 'success'}, 200

def handle_order_approved(event_data):
    """Handle when user approves the order"""
    order_id = event_data['resource']['id']
    user_id = event_data['resource']['custom_id']
    
    # Capture the order
    try:
        transaction = paypal_provider.capture_order(
            user_id=user_id,
            order_id=order_id,
            metadata={"captured_by": "webhook"}
        )
        print(f"Order captured: {transaction.id}")
    except Exception as e:
        print(f"Failed to capture order: {e}")

def handle_payment_completed(event_data):
    """Handle successful payment"""
    capture_id = event_data['resource']['id']
    print(f"Payment completed: {capture_id}")
    # Grant access to AI agent features

def handle_payment_denied(event_data):
    """Handle failed payment"""
    capture_id = event_data['resource']['id']
    print(f"Payment denied: {capture_id}")
    # Handle payment failure
```

### Webhook Events

Common PayPal webhook events to handle:

| Event Type | Description | Action |
|------------|-------------|--------|
| `CHECKOUT.ORDER.APPROVED` | User approved the order | Capture the order |
| `PAYMENT.CAPTURE.COMPLETED` | Payment completed successfully | Grant access, send confirmation |
| `PAYMENT.CAPTURE.DENIED` | Payment was denied | Notify user, retry logic |
| `PAYMENT.CAPTURE.REFUNDED` | Payment was refunded | Revoke access, handle refund |

## 💰 Refunds

### Process Refund

```python
# Full refund
refund_result = paypal_provider.refund_payment(
    transaction_id="transaction_123"
)

print(f"Refund ID: {refund_result['refund_id']}")
print(f"Status: {refund_result['status']}")
print(f"Amount: ${refund_result['amount']}")

# Partial refund
partial_refund = paypal_provider.refund_payment(
    transaction_id="transaction_123",
    amount=10.00  # Refund $10.00
)
```

## 🔍 Payment Verification

### Verify Payment Status

```python
# Verify a payment
is_verified = paypal_provider.verify_payment("transaction_123")
print(f"Payment verified: {is_verified}")

# Get payment status
status = paypal_provider.get_payment_status("transaction_123")
print(f"Payment status: {status}")
```

## 🔐 Security Best Practices

### API Credentials Management

```python
import os

# Use environment variables
paypal_provider = create_payment_provider(
    "paypal",
    client_id=os.getenv("PAYPAL_CLIENT_ID"),
    client_secret=os.getenv("PAYPAL_CLIENT_SECRET"),
    sandbox=True,
    return_url=os.getenv("PAYPAL_RETURN_URL"),
    cancel_url=os.getenv("PAYPAL_CANCEL_URL")
)

# Never hardcode credentials
# ❌ Bad
paypal_provider = create_payment_provider(
    "paypal",
    client_id="your_client_id_here",
    client_secret="your_client_secret_here"
)

# ✅ Good
paypal_provider = create_payment_provider(
    "paypal",
    client_id=os.getenv("PAYPAL_CLIENT_ID"),
    client_secret=os.getenv("PAYPAL_CLIENT_SECRET"),
    return_url=os.getenv("PAYPAL_RETURN_URL"),
    cancel_url=os.getenv("PAYPAL_CANCEL_URL")
)
```

### Webhook Security

```python
# Always verify webhook signatures
@app.route('/webhook', methods=['POST'])
def handle_webhook():
    try:
        is_valid = paypal_provider.verify_webhook_signature(
            payload=request.data.decode('utf-8'),
            headers=dict(request.headers)
        )
        
        if not is_valid:
            return {'error': 'Invalid signature'}, 400
    except Exception as e:
        return {'error': 'Webhook verification failed'}, 400
    
    # Process the event
    return {'status': 'success'}, 200
```

### Idempotency Keys

```python
import uuid

# Use idempotency keys for critical operations
idempotency_key = str(uuid.uuid4())

order_response = paypal_provider.create_order(
    user_id="user_123",
    amount=25.99,
    currency="USD",
    idempotency_key=idempotency_key
)
```

## 🧪 Fallback & Mock Mode

**Automatic Fallback:**  
If the `requests` library is not installed in your environment, the PayPal provider will automatically switch to "mock mode." In this mode:
- All payment, order, and refund operations return simulated/mock results.
- No real API calls are made to PayPal.
- This is ideal for local development, CI pipelines, and testing without real credentials.

**How it works:**
```python
# If requests is missing, fallback is automatic:
try:
    import requests
except ImportError:
    print("requests not installed: PayPal provider will use mock mode.")

paypal_provider = create_payment_provider(
    "paypal",
    client_id="any_value",
    client_secret="any_value",
    sandbox=True
)

# All methods will return mock results:
transaction = paypal_provider.process_payment(
    user_id="test_user",
    amount=10.0,
    currency="USD"
)
print(transaction.status)  # "completed" (mock)
print(transaction.metadata["mock_transaction"])  # True
```

**Tip:**  
You can deliberately test fallback mode by uninstalling `requests` in a virtual environment:
```bash
pip uninstall requests
```
Or by using a minimal Docker/CI image.

**Note:**
- A warning will be logged when fallback is activated.
- For more on simulated/test payments, see the [Mock Provider Guide](Mock-Provider-Guide.md).

## 🧪 Testing

### Sandbox Environment

```python
# Use sandbox for testing
paypal_provider = create_payment_provider(
    "paypal",
    client_id="your_sandbox_client_id",
    client_secret="your_sandbox_client_secret",
    sandbox=True,
    return_url="https://yourapp.com/success",
    cancel_url="https://yourapp.com/cancel"
)

# Test payment
transaction = paypal_provider.process_payment(
    user_id="test_user",
    amount=25.99,
    currency="USD",
    metadata={"test": True}
)
```

### Mock Mode

When the `requests` library is not available, the provider automatically falls back to mock mode:

```python
# Mock transactions for testing
transaction = paypal_provider._create_mock_transaction(
    user_id="test_user",
    amount=25.99,
    currency="USD",
    metadata={"mock": True}
)
```

## 🚨 Error Handling

### Common Errors

```python
from aiagent_payments.exceptions import PaymentFailed, ProviderError, ValidationError

try:
    transaction = paypal_provider.process_payment(
        user_id="user_123",
        amount=25.99,
        currency="USD"
    )
except ValidationError as e:
    print(f"Validation error: {e}")
except PaymentFailed as e:
    print(f"Payment failed: {e}")
except ProviderError as e:
    print(f"Provider error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Error Recovery

```python
import time

def process_payment_with_retry(user_id, amount, currency, max_retries=3):
    for attempt in range(max_retries):
        try:
            transaction = paypal_provider.process_payment(
                user_id=user_id,
                amount=amount,
                currency=currency
            )
            return transaction
        except ProviderError as e:
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1} failed: {e}")
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise e
```

## 🔧 Recent Updates

### PayPal Provider Factory Fix (Latest)

**What was fixed:**
- The `create_payment_provider` factory function now properly forwards all configuration parameters (`return_url`, `cancel_url`, `webhook_id`, `timeout`) to the PayPal provider constructor.

**Before (Broken):**
```python
# This would fail with "return_url cannot be empty" error
provider = create_payment_provider(
    "paypal",
    client_id="your_client_id",
    client_secret="your_client_secret",
    return_url="https://yourapp.com/success",  # ❌ Not forwarded
    cancel_url="https://yourapp.com/cancel"    # ❌ Not forwarded
)
```

**After (Fixed):**
```python
# This now works correctly
provider = create_payment_provider(
    "paypal",
    client_id="your_client_id",
    client_secret="your_client_secret",
    return_url="https://yourapp.com/success",  # ✅ Properly forwarded
    cancel_url="https://yourapp.com/cancel"    # ✅ Properly forwarded
)
```

**What this means for you:**
- No more "return_url cannot be empty" errors when using the factory function
- Cleaner, more reliable provider configuration
- Better developer experience with improved error messages

## 📚 Additional Resources

- [PayPal Developer Documentation](https://developer.paypal.com/)
- [PayPal Sandbox Testing](https://developer.paypal.com/docs/api-basics/sandbox/)
- [PayPal Webhook Events](https://developer.paypal.com/docs/api-basics/notifications/webhooks/event-names/)
- [Common Errors Guide](../Common-Errors.md)
- [Getting Started Guide](../Getting-Started.md) 
