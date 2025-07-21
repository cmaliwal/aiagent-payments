# Mock Provider Guide

A comprehensive guide to using the Mock payment provider for testing, development, and demonstration purposes.

## 🎯 Overview

The Mock provider is a simulated payment processor that mimics real payment provider behavior without making actual API calls. It's perfect for development, testing, and demonstrations.

## 🚀 Quick Start

### Basic Setup

```python
from aiagent_payments import PaymentProcessor

# Initialize Mock processor (no API keys needed)
processor = PaymentProcessor(provider="mock")

# Process a simple payment
result = processor.process_payment(
    amount=1000,  # $10.00 in cents
    currency="usd",
    description="AI Agent Consultation"
)

print(f"Payment ID: {result.payment_id}")
print(f"Status: {result.status}")
print(f"Amount: ${result.amount / 100:.2f}")
```

### No Configuration Required

```python
# Mock provider works out of the box
processor = PaymentProcessor(provider="mock")

# No environment variables needed
# No API keys required
# No network calls made
```

## 💳 Payment Methods

### Standard Payments

```python
# Process a payment (always succeeds)
result = processor.process_payment(
    amount=1000,
    currency="usd",
    description="Test payment"
)

print(f"Payment ID: {result.payment_id}")
print(f"Status: {result.status}")  # Always "succeeded"
print(f"Amount: ${result.amount / 100:.2f}")
```

### Payment Intents

```python
# Create a payment intent
payment_intent = processor.create_payment_intent(
    amount=1000,
    currency="usd",
    description="Test payment intent"
)

print(f"Payment Intent ID: {payment_intent.payment_id}")
print(f"Status: {payment_intent.status}")
print(f"Client Secret: {payment_intent.client_secret}")
```

### Checkout Sessions

```python
# Create a checkout session
session = processor.create_checkout_session(
    amount=1000,
    currency="usd",
    description="Test checkout session",
    success_url="https://yourapp.com/success",
    cancel_url="https://yourapp.com/cancel"
)

print(f"Session ID: {session.session_id}")
print(f"Checkout URL: {session.url}")
```

## 👥 Customer Management

### Create Customer

```python
# Create a customer
customer = processor.create_customer(
    email="test@example.com",
    name="Test User",
    metadata={"test": True}
)

print(f"Customer ID: {customer.customer_id}")
print(f"Email: {customer.email}")
print(f"Name: {customer.name}")
```

### Retrieve Customer

```python
# Get customer details
customer = processor.get_customer("mock_customer_123")

print(f"Email: {customer.email}")
print(f"Name: {customer.name}")
print(f"Created: {customer.created}")
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

## 🔄 Subscriptions

### Create Subscription

```python
# Create a subscription
subscription = processor.create_subscription(
    customer_id="mock_customer_123",
    plan_id="mock_plan_456",
    amount=2000,  # $20.00/month
    currency="usd"
)

print(f"Subscription ID: {subscription.subscription_id}")
print(f"Status: {subscription.status}")
print(f"Amount: ${subscription.amount / 100:.2f}")
```

### Manage Subscriptions

```python
# Cancel subscription
cancelled_subscription = processor.cancel_subscription(
    subscription_id="mock_sub_123"
)

# Reactivate subscription
reactivated_subscription = processor.reactivate_subscription(
    subscription_id="mock_sub_123"
)

# Update subscription
updated_subscription = processor.update_subscription(
    subscription_id="mock_sub_123",
    plan_id="mock_new_plan"
)
```

## 🧪 Testing Scenarios

### Success Scenarios

```python
# Test successful payments
amounts = [100, 500, 1000, 5000, 10000]
currencies = ["usd", "eur", "gbp", "cad", "aud"]

for amount in amounts:
    for currency in currencies:
        result = processor.process_payment(
            amount=amount,
            currency=currency,
            description=f"Test payment {amount} {currency}"
        )
        print(f"✅ {currency.upper()}: ${amount/100:.2f} - {result.status}")
```

### Error Simulation

```python
# Mock provider can simulate errors for testing
def test_error_scenarios():
    # Test with invalid amount
    try:
        result = processor.process_payment(
            amount=-100,  # Negative amount
            currency="usd",
            description="Invalid amount test"
        )
    except ValueError as e:
        print(f"✅ Caught error: {e}")
    
    # Test with invalid currency
    try:
        result = processor.process_payment(
            amount=1000,
            currency="invalid",  # Invalid currency
            description="Invalid currency test"
        )
    except ValueError as e:
        print(f"✅ Caught error: {e}")
```

### Webhook Testing

```python
# Simulate webhook events
def test_webhook_events():
    # Simulate successful payment webhook
    webhook_data = {
        "type": "payment.succeeded",
        "data": {
            "payment_id": "mock_payment_123",
            "amount": 1000,
            "currency": "usd"
        }
    }
    
    # Process webhook
    event = processor.parse_webhook(webhook_data)
    print(f"✅ Webhook processed: {event.type}")
```

## 🔧 Configuration Options

### Custom Success Rate

```python
# Configure mock provider behavior
processor = PaymentProcessor(
    provider="mock",
    config={
        "success_rate": 0.8,  # 80% success rate
        "delay_ms": 100,      # 100ms delay
        "generate_errors": True
    }
)

# Test with custom configuration
for i in range(10):
    try:
        result = processor.process_payment(
            amount=1000,
            currency="usd",
            description=f"Test {i+1}"
        )
        print(f"✅ Payment {i+1}: {result.status}")
    except Exception as e:
        print(f"❌ Payment {i+1}: {e}")
```

### Error Simulation

```python
# Configure specific error scenarios
processor = PaymentProcessor(
    provider="mock",
    config={
        "error_scenarios": {
            "insufficient_funds": 0.1,    # 10% insufficient funds
            "card_declined": 0.05,        # 5% card declined
            "network_error": 0.02         # 2% network error
        }
    }
)
```

## 📊 Analytics and Reporting

### Payment Statistics

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

## 🧪 Unit Testing

### Test Setup

```python
import pytest
from aiagent_payments import PaymentProcessor

@pytest.fixture
def mock_processor():
    """Create a mock processor for testing."""
    return PaymentProcessor(provider="mock")

class TestMockProvider:
    """Test cases for Mock provider."""
    
    def test_process_payment_success(self, mock_processor):
        """Test successful payment processing."""
        result = mock_processor.process_payment(
            amount=1000,
            currency="usd",
            description="Test payment"
        )
        
        assert result.status == "succeeded"
        assert result.amount == 1000
        assert result.currency == "usd"
        assert result.payment_id.startswith("mock_")
    
    def test_create_customer(self, mock_processor):
        """Test customer creation."""
        customer = mock_processor.create_customer(
            email="test@example.com",
            name="Test User"
        )
        
        assert customer.email == "test@example.com"
        assert customer.name == "Test User"
        assert customer.customer_id.startswith("mock_")
    
    def test_create_subscription(self, mock_processor):
        """Test subscription creation."""
        subscription = mock_processor.create_subscription(
            customer_id="mock_customer_123",
            plan_id="mock_plan_456",
            amount=2000,
            currency="usd"
        )
        
        assert subscription.status == "active"
        assert subscription.amount == 2000
        assert subscription.subscription_id.startswith("mock_")
```

### Integration Testing

```python
def test_payment_workflow(mock_processor):
    """Test complete payment workflow."""
    # 1. Create customer
    customer = mock_processor.create_customer(
        email="user@example.com",
        name="Test User"
    )
    
    # 2. Process payment
    payment = mock_processor.process_payment(
        amount=1000,
        currency="usd",
        description="Test payment"
    )
    
    # 3. Create subscription
    subscription = mock_processor.create_subscription(
        customer_id=customer.customer_id,
        plan_id="mock_plan",
        amount=2000,
        currency="usd"
    )
    
    # 4. Verify all operations succeeded
    assert customer.customer_id is not None
    assert payment.status == "succeeded"
    assert subscription.status == "active"
```

## 🔄 Development Workflow

### Local Development

```python
# Use mock provider for local development
def create_development_processor():
    """Create processor for development environment."""
    if os.getenv("ENVIRONMENT") == "development":
        return PaymentProcessor(provider="mock")
    else:
        return PaymentProcessor(
            provider="stripe",
            api_key=os.getenv("STRIPE_SECRET_KEY")
        )

# Use in your application
processor = create_development_processor()
```

### CI/CD Testing

```python
# Use mock provider in CI/CD pipelines
def test_payment_integration():
    """Test payment integration without external dependencies."""
    processor = PaymentProcessor(provider="mock")
    
    # Test all payment operations
    result = processor.process_payment(
        amount=1000,
        currency="usd",
        description="CI/CD test"
    )
    
    assert result.status == "succeeded"
    return result
```

## 📱 Demo Applications

### Simple Demo

```python
def demo_payment_flow():
    """Demonstrate payment flow to stakeholders."""
    processor = PaymentProcessor(provider="mock")
    
    print("🤖 AI Agent Payment Demo")
    print("=" * 30)
    
    # Create customer
    customer = processor.create_customer(
        email="demo@example.com",
        name="Demo User"
    )
    print(f"✅ Customer created: {customer.email}")
    
    # Process payment
    payment = processor.process_payment(
        amount=2500,  # $25.00
        currency="usd",
        description="AI Agent Consultation"
    )
    print(f"✅ Payment processed: ${payment.amount/100:.2f}")
    
    # Create subscription
    subscription = processor.create_subscription(
        customer_id=customer.customer_id,
        plan_id="pro_plan",
        amount=5000,  # $50.00/month
        currency="usd"
    )
    print(f"✅ Subscription created: ${subscription.amount/100:.2f}/month")
    
    print("\n🎉 Demo completed successfully!")
```

### Interactive Demo

```python
def interactive_demo():
    """Interactive demo for presentations."""
    processor = PaymentProcessor(provider="mock")
    
    while True:
        print("\n🤖 AI Agent Payments Demo")
        print("1. Process payment")
        print("2. Create customer")
        print("3. Create subscription")
        print("4. View statistics")
        print("5. Exit")
        
        choice = input("\nSelect option (1-5): ")
        
        if choice == "1":
            amount = int(input("Enter amount in cents: "))
            result = processor.process_payment(
                amount=amount,
                currency="usd",
                description="Demo payment"
            )
            print(f"✅ Payment {result.status}: {result.payment_id}")
        
        elif choice == "2":
            email = input("Enter email: ")
            name = input("Enter name: ")
            customer = processor.create_customer(email=email, name=name)
            print(f"✅ Customer created: {customer.customer_id}")
        
        elif choice == "3":
            customer_id = input("Enter customer ID: ")
            amount = int(input("Enter monthly amount in cents: "))
            subscription = processor.create_subscription(
                customer_id=customer_id,
                plan_id="demo_plan",
                amount=amount,
                currency="usd"
            )
            print(f"✅ Subscription created: {subscription.subscription_id}")
        
        elif choice == "4":
            stats = processor.get_payment_statistics()
            print(f"📊 Total payments: {stats.total_payments}")
            print(f"📊 Total amount: ${stats.total_amount/100:.2f}")
        
        elif choice == "5":
            print("👋 Thanks for the demo!")
            break
```

## 🔧 Advanced Features

### Custom Payment IDs

```python
# Generate custom payment IDs
import uuid

def create_custom_payment_id():
    return f"demo_{uuid.uuid4().hex[:8]}"

# Use in mock provider
processor = PaymentProcessor(
    provider="mock",
    config={
        "custom_id_generator": create_custom_payment_id
    }
)

result = processor.process_payment(
    amount=1000,
    currency="usd",
    description="Custom ID test"
)

print(f"Payment ID: {result.payment_id}")  # e.g., "demo_a1b2c3d4"
```

### Simulated Delays

```python
# Add realistic delays
processor = PaymentProcessor(
    provider="mock",
    config={
        "delay_ms": 500,  # 500ms delay
        "random_delay": True  # Add random variation
    }
)

# This will take ~500ms to complete
result = processor.process_payment(
    amount=1000,
    currency="usd",
    description="Delayed payment"
)
```

## 📚 Best Practices

### Development Best Practices

1. **Use Mock for Development**: Always use mock provider during development
2. **Test All Scenarios**: Test both success and error scenarios
3. **Simulate Real Conditions**: Use realistic delays and error rates
4. **Document Test Cases**: Keep track of what you're testing

### Testing Best Practices

1. **Isolate Tests**: Each test should be independent
2. **Use Fixtures**: Create reusable test fixtures
3. **Test Edge Cases**: Test boundary conditions and error scenarios
4. **Mock External Dependencies**: Don't rely on external services in tests

### Demo Best Practices

1. **Keep It Simple**: Focus on core functionality
2. **Show Real Value**: Demonstrate actual use cases
3. **Be Interactive**: Allow audience participation
4. **Prepare Fallbacks**: Have backup demos ready

## 🚨 Limitations

### What Mock Provider Doesn't Do

- **Real Payments**: No actual money is transferred
- **External APIs**: No network calls to payment providers
- **Real Security**: No actual security validation
- **Production Use**: Not suitable for production environments

### When to Use Real Providers

- **Production**: Always use real providers in production
- **Integration Testing**: Test with real providers for integration
- **Security Testing**: Test security with real providers
- **Performance Testing**: Test performance with real APIs

## 📚 Additional Resources

### Related Documentation
- [Getting Started](Getting-Started) - Quick start guide
- [Installation Guide](Installation-Guide) - Setup instructions
- [Stripe Deep Dive](Stripe-Deep-Dive) - Real Stripe integration
- [PayPal Integration](PayPal-Integration) - Real PayPal integration

### Examples
- [Basic Usage](https://github.com/cmaliwal/aiagent-payments/tree/main/examples/basic)
- [Testing Examples](https://github.com/cmaliwal/aiagent-payments/tree/main/examples/advanced)
- [Demo Applications](https://github.com/cmaliwal/aiagent-payments/tree/main/examples)

### Community Support
- [GitHub Issues](https://github.com/cmaliwal/aiagent-payments/issues)
- [Discussions](https://github.com/cmaliwal/aiagent-payments/discussions)

---

**Ready to start testing?** The Mock provider is perfect for development, testing, and demonstrations! 🚀 