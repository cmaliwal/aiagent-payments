# Getting Started Guide

Welcome to the AI Agent Payments SDK! This guide will help you get up and running in minutes.

## 🎯 What You'll Learn

By the end of this guide, you'll have:
- ✅ Installed the SDK
- ✅ Set up your first payment plan
- ✅ Created a subscription
- ✅ Implemented access control
- ✅ Processed your first payment

## 📋 Prerequisites

- **Python 3.10+** (required)
- **pip** (Python package installer)
- **Basic Python knowledge**
- **Optional**: Payment provider accounts (Stripe, PayPal, etc.)

## 🚀 Step 1: Installation

### Install the SDK

```bash
pip install aiagent-payments
```

### Install Optional Dependencies

For specific payment providers:

```bash
# Stripe support
pip install aiagent-payments[stripe]

# PayPal support
pip install aiagent-payments[paypal]

# Crypto support (USDT ERC-20)
pip install aiagent-payments[crypto]

# Database support
pip install aiagent-payments[database]

# Web framework support
pip install aiagent-payments[web]
```

## 🚀 Step 2: Basic Setup

### Import the SDK

```python
from aiagent_payments import PaymentManager, PaymentPlan
from aiagent_payments.providers import create_payment_provider
from aiagent_payments.storage import MemoryStorage
from aiagent_payments.models import PaymentType, BillingPeriod
```

### Initialize Components

```python
# Create a payment provider (start with mock for testing)
provider = create_payment_provider("mock")

# Create storage backend (memory for development)
storage = MemoryStorage()

# Create payment manager
manager = PaymentManager(
    storage=storage,
    payment_provider=provider
)
```

### Provider Configuration Examples

```python
# Mock provider (for testing)
mock_provider = create_payment_provider("mock")

# Stripe provider
stripe_provider = create_payment_provider(
    "stripe",
    api_key="sk_test_your_stripe_key"
)

# PayPal provider (with required URLs)
paypal_provider = create_payment_provider(
    "paypal",
    client_id="your_paypal_client_id",
    client_secret="your_paypal_client_secret",
    sandbox=True,  # Use sandbox for testing
    return_url="https://yourapp.com/success",
    cancel_url="https://yourapp.com/cancel"
)

# Crypto provider (USDT on Ethereum)
crypto_provider = create_payment_provider(
    "crypto",
    wallet_address="0xYourWalletAddress",
    infura_project_id="your_infura_project_id",
    network="sepolia"  # Use testnet for testing
)
```

## 🚀 Step 3: Create Payment Plans

### Define Your Plans

```python
# Freemium plan
freemium_plan = PaymentPlan(
    id="freemium",
    name="Freemium",
    description="Free tier with limited usage",
    payment_type=PaymentType.FREEMIUM,
    price=0.0,
    free_requests=5,
    features=["basic_ai_response", "simple_analysis"]
)

# Pro subscription plan
pro_plan = PaymentPlan(
    id="pro",
    name="Pro Subscription",
    description="Professional subscription with unlimited usage",
    payment_type=PaymentType.SUBSCRIPTION,
    price=29.99,
    currency="USD",
    billing_period=BillingPeriod.MONTHLY,
    requests_per_period=1000,
    features=["advanced_ai_response", "complex_analysis", "priority_support"]
)

# Pay-per-use plan
pay_per_use_plan = PaymentPlan(
    id="pay_per_use",
    name="Pay per Use",
    description="Pay only for what you use",
    payment_type=PaymentType.PAY_PER_USE,
    price=0.0,
    price_per_request=0.01,
    features=["all_features"]
)
```

### Register Plans

```python
# Add plans to the manager
manager.create_payment_plan(freemium_plan)
manager.create_payment_plan(pro_plan)
manager.create_payment_plan(pay_per_use_plan)

print("✅ Payment plans created successfully!")
```

## 🚀 Step 4: Implement Access Control

### Create Your AI Functions

```python
# Basic AI response function
@manager.paid_feature(feature_name="basic_ai_response", cost=0.01)
def basic_ai_response(user_id: str, prompt: str):
    """Basic AI response function."""
    return f"Basic AI response to: {prompt}"

# Advanced AI response function
@manager.paid_feature(feature_name="advanced_ai_response", cost=0.05)
def advanced_ai_response(user_id: str, prompt: str):
    """Advanced AI response function."""
    return f"Advanced AI response to: {prompt} (with enhanced processing)"

# Subscription-only feature
@manager.subscription_required(plan_id="pro")
def complex_analysis(user_id: str, data: str):
    """Complex analysis function (subscription only)."""
    return f"Complex analysis of: {data} (Pro feature)"

# Usage-limited feature
@manager.usage_limit(max_uses=3, feature_name="premium_feature")
def premium_feature(user_id: str, input_data: str):
    """Premium feature with usage limit."""
    return f"Premium feature result for: {input_data}"
```

## 🚀 Step 5: Subscribe Users

### Subscribe to a Plan

```python
# Subscribe a user to the pro plan
user_id = "user@example.com"
subscription = manager.subscribe_user(user_id, "pro")
print(f"✅ User {user_id} subscribed to Pro plan: {subscription.id}")
```

### Check Subscription Status

```python
# Get user's subscription
subscription = manager.get_user_subscription(user_id)
if subscription and subscription.is_active():
    print(f"✅ User {user_id} has active subscription")
else:
    print(f"❌ User {user_id} has no active subscription")
```

## 🚀 Step 6: Test Your Integration

### Test Different User Scenarios

```python
# Test freemium user
freemium_user = "freemium@example.com"
try:
    # Should work (within free limit)
    for i in range(3):
        result = basic_ai_response(freemium_user, f"Test prompt {i + 1}")
        print(f"✅ Basic AI response {i + 1}: {result}")
    
    # Should fail (exceeded free limit)
    result = basic_ai_response(freemium_user, "Test prompt 6")
    print(f"❌ This should fail: {result}")
except Exception as e:
    print(f"❌ Expected error: {e}")

# Test pro subscription user
pro_user = "pro@example.com"
manager.subscribe_user(pro_user, "pro")

try:
    # Should work (subscription active)
    result = complex_analysis(pro_user, "Test data")
    print(f"✅ Complex analysis: {result}")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
```

## 🚀 Step 7: Process Payments

### Handle Payment Processing

```python
# After user completes payment through your UI
def handle_payment_completion(user_id: str, payment_amount: float):
    """Handle payment completion from your payment provider."""
    try:
        # Process the payment through the SDK
        transaction = manager.process_payment(
            user_id=user_id,
            amount=payment_amount,
            currency="USD",
            metadata={"source": "web_checkout"}
        )
        
        print(f"✅ Payment processed: {transaction.id}")
        
        # Subscribe user to plan
        subscription = manager.subscribe_user(user_id, "pro")
        print(f"✅ User subscribed: {subscription.id}")
        
        return True
    except Exception as e:
        print(f"❌ Payment processing failed: {e}")
        return False

# Example usage
success = handle_payment_completion("user@example.com", 29.99)
```

## 🔧 Environment Configuration

### Set Up Environment Variables

Create a `.env` file in your project root:

```bash
# Payment Provider Keys
STRIPE_API_KEY=sk_test_your_stripe_key
PAYPAL_CLIENT_ID=your_paypal_client_id
PAYPAL_CLIENT_SECRET=your_paypal_client_secret
INFURA_PROJECT_ID=your_infura_project_id

# PayPal URLs
PAYPAL_RETURN_URL=https://yourapp.com/success
PAYPAL_CANCEL_URL=https://yourapp.com/cancel

# Development Mode (for crypto provider)
AIAgentPayments_DevMode=1
```

### Load Environment Variables

```python
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Use environment variables for configuration
provider = create_payment_provider(
    "paypal",
    client_id=os.getenv("PAYPAL_CLIENT_ID"),
    client_secret=os.getenv("PAYPAL_CLIENT_SECRET"),
    return_url=os.getenv("PAYPAL_RETURN_URL"),
    cancel_url=os.getenv("PAYPAL_CANCEL_URL"),
    sandbox=True
)
```

## 🧪 Testing Best Practices

### Use Test Mode

```python
# Always use test/sandbox mode for development
stripe_provider = create_payment_provider(
    "stripe",
    api_key="sk_test_..."  # Use test key
)

paypal_provider = create_payment_provider(
    "paypal",
    client_id="your_sandbox_client_id",
    client_secret="your_sandbox_client_secret",
    sandbox=True,  # Use sandbox
    return_url="https://yourapp.com/success",
    cancel_url="https://yourapp.com/cancel"
)

crypto_provider = create_payment_provider(
    "crypto",
    wallet_address="0xYourTestWallet",
    infura_project_id="your_infura_project_id",
    network="sepolia"  # Use testnet
)
```

### Test Different Scenarios

```python
# Test payment processing
def test_payment_scenarios():
    test_cases = [
        {"user": "test1@example.com", "amount": 10.00},
        {"user": "test2@example.com", "amount": 25.99},
        {"user": "test3@example.com", "amount": 99.99},
    ]
    
    for case in test_cases:
        try:
            transaction = manager.process_payment(
                user_id=case["user"],
                amount=case["amount"],
                currency="USD"
            )
            print(f"✅ Payment successful: {transaction.id}")
        except Exception as e:
            print(f"❌ Payment failed: {e}")

# Run tests
test_payment_scenarios()
```

## 🚨 Common Issues & Solutions

### PayPal Configuration Issues

**Issue:** "return_url cannot be empty" error

**Solution:** Always provide return_url and cancel_url when using PayPal:

```python
# ✅ Correct
paypal_provider = create_payment_provider(
    "paypal",
    client_id="your_client_id",
    client_secret="your_client_secret",
    return_url="https://yourapp.com/success",  # Required
    cancel_url="https://yourapp.com/cancel"    # Required
)

# ❌ Wrong
paypal_provider = create_payment_provider(
    "paypal",
    client_id="your_client_id",
    client_secret="your_client_secret"
    # Missing URLs
)
```

### Crypto Provider Storage Issues

**Issue:** "In-memory storage not allowed in production mode"

**Solution:** Set development mode or use persistent storage:

```python
# For development
import os
os.environ["AIAgentPayments_DevMode"] = "1"

# For production
from aiagent_payments.storage import DatabaseStorage
storage = DatabaseStorage(database_url="sqlite:///payments.db")
```

## 📚 Next Steps

Now that you have the basics working:

1. **Explore Advanced Features:**
   - [PayPal Integration Guide](PayPal-Integration.md)
   - [Stripe Deep Dive](Stripe-Deep-Dive.md)
   - [Crypto Payments Guide](Crypto-Payments-Guide.md)

2. **Learn About Error Handling:**
   - [Common Errors Guide](Common-Errors.md)

3. **Check Out Examples:**
   - [Basic Examples](../examples/basic/)
   - [Advanced Examples](../examples/advanced/)
   - [Real-World Integrations](../examples/real_world/)

4. **Production Deployment:**
   - Use live API keys
   - Set up proper storage backends
   - Configure webhooks
   - Implement proper error handling

## 🆘 Need Help?

- **Documentation:** Check the [wiki](../wiki/) for detailed guides
- **Examples:** Browse the [examples](../examples/) directory
- **Issues:** Report bugs on [GitHub](https://github.com/cmaliwal/aiagent-payments/issues)
- **Discussions:** Ask questions in [GitHub Discussions](https://github.com/cmaliwal/aiagent-payments/discussions)

---

**Happy coding!** 🚀 Your AI agent is now ready to accept payments and manage subscriptions! 