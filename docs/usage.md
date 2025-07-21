# Usage Guide

## Importing the SDK

```python
from aiagent_payments import PaymentManager, UsageTracker, SubscriptionManager
from aiagent_payments.models import PaymentPlan, PaymentType, BillingPeriod
from aiagent_payments.storage import MemoryStorage, FileStorage, DatabaseStorage
from aiagent_payments.providers import create_payment_provider, StripeProvider, PayPalProvider, CryptoProvider, MockProvider
from aiagent_payments.exceptions import PaymentFailed, UsageLimitExceeded, ValidationError
```

## Creating Payment Plans

See the README for detailed examples. You can create freemium, subscription, and pay-per-use plans.

## Using Decorators

Decorate your agent functions with `@pm.paid_feature`, `@pm.subscription_required`, or `@pm.usage_limit` to enforce access control and payments.

## Health Monitoring and Capabilities

The SDK now provides comprehensive health monitoring and capability reporting for both payment providers and storage backends.

### Provider Health Checks

```python
from aiagent_payments.providers import StripeProvider

stripe_provider = StripeProvider(api_key="sk_test_...")

# Check provider health
status = stripe_provider.check_health()
print(f"Provider healthy: {status.is_healthy}")
print(f"Response time: {status.response_time_ms}ms")

# Get provider capabilities
capabilities = stripe_provider.get_capabilities()
print(f"Supports refunds: {capabilities.supports_refunds}")
print(f"Supported currencies: {capabilities.supported_currencies}")

# Get comprehensive provider info
info = stripe_provider.get_provider_info()
print(f"Provider info: {info}")
```

### Storage Health Checks

```python
from aiagent_payments.storage import DatabaseStorage

storage = DatabaseStorage("payments.db")

# Check storage health
status = storage.check_health()
print(f"Storage healthy: {status.is_healthy}")

# Get storage capabilities
capabilities = storage.get_capabilities()
print(f"Supports transactions: {capabilities.supports_transactions}")
print(f"Supports encryption: {capabilities.supports_encryption}")

# Get comprehensive storage info
info = storage.get_storage_info()
print(f"Storage info: {info}")
```

## Enhanced Validation and Error Handling

The SDK now includes comprehensive input validation and improved error handling.

### Input Validation

```python
from aiagent_payments import PaymentManager
from aiagent_payments.exceptions import ValidationError

pm = PaymentManager(storage=storage, payment_provider=provider)

try:
    # This will raise ValidationError for empty user_id
    pm.check_access("", "feature_name")
except ValidationError as e:
    print(f"Validation error: {e}")

try:
    # This will raise ValidationError for empty feature
    pm.record_usage("user123", "", 0.01)
except ValidationError as e:
    print(f"Validation error: {e}")
```

### Common Validation Errors

The SDK provides detailed validation errors to help you debug issues quickly. Here are the most common validation errors and how to fix them:

#### PaymentPlan Validation Errors

| Error Message | Cause | Fix |
|---------------|-------|-----|
| `Plan ID is required and must be a string` | Missing or invalid plan ID | Provide a non-empty string ID |
| `Plan name is required and must be a string` | Missing or invalid plan name | Provide a non-empty string name |
| `Plan price cannot be negative` | Negative price value | Use a non-negative price |
| `Currency USD is not supported` | Unsupported currency | Use one of: USD, EUR, USDC, USDT, etc. |
| `Price 0.10 USDC is below the minimum 0.50 USDC` | Amount below stablecoin minimum | Increase amount to meet minimum (0.50 for stablecoins) |
| `Invalid payment type: invalid` | Invalid payment type | Use: pay_per_use, subscription, or freemium |
| `Invalid billing period: invalid` | Invalid billing period | Use: daily, weekly, monthly, or yearly |

#### PaymentTransaction Validation Errors

| Error Message | Cause | Fix |
|---------------|-------|-----|
| `Transaction ID is required and must be a string` | Missing or invalid transaction ID | Provide a non-empty string ID |
| `Amount must be a non-negative number` | Negative or invalid amount | Use a non-negative number |
| `Amount 0.10 USDC is below the minimum 0.50 USDC` | Amount below stablecoin minimum | Increase amount to meet minimum |
| `Cannot mark transaction as completed from status 'completed'` | Invalid status transition | Only pending transactions can be completed |
| `Invalid ISO 8601 datetime format for created_at` | Malformed datetime string | Use ISO 8601 format: YYYY-MM-DDTHH:MM:SS |

#### Subscription Validation Errors

| Error Message | Cause | Fix |
|---------------|-------|-----|
| `Subscription ID is required and must be a string` | Missing or invalid subscription ID | Provide a non-empty string ID |
| `Cannot change subscription status from expired to active` | Invalid status transition | Use set_status() method for valid transitions |
| `End date cannot be before start date` | Invalid date range | Ensure end_date is after start_date |
| `Metadata contains non-JSON-serializable content` | Non-serializable metadata | Use only JSON-serializable types (str, int, float, bool, list, dict, None) |

#### UsageRecord Validation Errors

| Error Message | Cause | Fix |
|---------------|-------|-----|
| `UsageRecord ID is required and must be a string` | Missing or invalid usage record ID | Provide a non-empty string ID |
| `Feature is required and must be a string` | Missing or invalid feature name | Provide a non-empty string feature name |
| `Cost cannot be negative` | Negative cost value | Use a non-negative cost or None for free usage |

#### Currency and Amount Guidelines

- **Fiat Currencies**: Minimum 0.01 (USD, EUR, GBP, etc.)
- **Stablecoins**: Minimum 0.50 (USDC, USDT, DAI, etc.)
- **Crypto**: Varies by currency (BTC: 0.0001, ETH: 0.001, etc.)
- **Supported Currencies**: USD, EUR, USDC, USDT, DAI, BTC, ETH, and more

#### Input Sanitization Requirements

All string fields are automatically sanitized to prevent security vulnerabilities:

- **Maximum Lengths**: IDs (100 chars), Names/Features (255 chars), Payment Methods (100 chars)
- **Invalid Characters**: `<`, `>`, `"`, `'` are not allowed in any string field
- **Empty Strings**: All required string fields must not be empty or whitespace-only

#### Example Error Handling

```python
from aiagent_payments.exceptions import ValidationError

try:
    plan = PaymentPlan(
        id="plan_123",
        name="Premium Plan",
        price=9.99,
        currency="USD"
    )
except ValidationError as e:
    print(f"Validation error: {e}")
    print(f"Field: {e.field}")
    print(f"Value: {e.value}")
    # Handle the error appropriately
```

#### Common Validation Error Patterns

| Error Type | Pattern | Example |
|------------|---------|---------|
| **String Validation** | `{field} must be a string` | `Plan ID must be a string` |
| **Length Validation** | `{field} exceeds maximum length of {max} characters` | `Plan name exceeds maximum length of 255 characters` |
| **Character Validation** | `{field} contains invalid characters` | `User ID contains invalid characters` |
| **Currency Validation** | `Currency {currency} is not supported` | `Currency XYZ is not supported` |
| **Amount Validation** | `{field} {amount} {currency} is below the minimum {min} {currency}` | `Cost 0.10 USDC is below the minimum 0.50 USDC` |
| **Status Validation** | `Cannot initialize subscription with status '{status}'` | `Cannot initialize subscription with status 'expired'` |
| **Datetime Validation** | `Invalid ISO 8601 datetime format for {field}` | `Invalid ISO 8601 datetime format for timestamp` |

#### Status Transition Rules

**PaymentTransaction Status Transitions:**
- `pending` → `completed` or `failed`
- `completed` → `refunded` or `failed`
- `failed` → (no further transitions)
- `refunded` → (no further transitions)

**Subscription Status Transitions:**
- `active` → `cancelled`, `expired`, or `suspended`
- `suspended` → `active` or `cancelled`
- `cancelled` → (no further transitions)
- `expired` → (no further transitions)

### Usage Limit Enforcement

```python
from aiagent_payments.exceptions import UsageLimitExceeded

try:
    # This will raise UsageLimitExceeded if user exceeds freemium limit
    result = pm.paid_feature("premium_analysis")(user_id, data)
except UsageLimitExceeded as e:
    print(f"Usage limit exceeded: {e}")
    print(f"Current usage: {e.current_usage}")
    print(f"Limit: {e.limit}")
```

## CLI Usage

Run `python cli/main.py --help` for available commands.

### Enabling/Disabling Storage Backends and Providers

You can control which storage backends and payment providers are available by editing `aiagent_payments/config.py`:

```python
ENABLED_STORAGE = ["memory", "file", "database"]  # Only allow these storage backends
ENABLED_PROVIDERS = ["mock", "stripe", "paypal", "crypto"]  # Only allow these providers
```

Or override via environment variables:

```bash
export AIAgentPayments_EnabledStorage="memory,file,database"
export AIAgentPayments_EnabledProviders="mock,stripe,paypal,crypto"
```

If a disabled backend/provider is selected, the CLI and SDK will show an error and exit. Only enabled providers/storage are importable and usable; others will raise errors if used.

## Advanced Features

### Transaction Support

Some storage backends support database transactions:

```python
from aiagent_payments.storage import DatabaseStorage

storage = DatabaseStorage("payments.db")

if storage.supports_transactions():
    # Begin a transaction
    transaction = storage.begin_transaction()
    try:
        # Perform multiple operations
        storage.save_payment_plan(plan1)
        storage.save_payment_plan(plan2)
        # Commit transaction
        transaction.commit()
    except Exception:
        # Rollback on error
        transaction.rollback()
        raise
```

### Backup Support

Some storage backends support data backup:

```python
if storage.capabilities.supports_backup:
    storage.backup_data("/path/to/backup.json")
```

### Search Support

Some storage backends support searching records:

```python
if storage.capabilities.supports_search:
    results = storage.search_records(
        query="premium",
        record_type="payment_plans",
        limit=10
    )
```

## Extending the SDK

- Add new payment providers by subclassing `PaymentProvider` and implementing required methods including `_get_capabilities()`, `_validate_configuration()`, and `_perform_health_check()`.
- Add new storage backends by subclassing `StorageBackend` and implementing required methods including `_get_capabilities()`, `_validate_configuration()`, and `_perform_health_check()`.
- Register new components in `__init__.py` and config.
- Contribute improvements via pull requests!

## More
- See `examples/basic/basic_usage.py` for a full demo.
- See `examples/advanced/advanced_usage.py` for advanced features.
- See `tests/unit/`, `tests/integration/`, and `tests/functional/` for test cases.
- See `docs/local_setup.md` for development setup.

## USDT Crypto & PayPal Payments: API Keys Required

For USDT ERC-20 payments and PayPal, set your API keys in a `.env` file or as environment variables:

```
INFURA_PROJECT_ID=your_infura_project_id_here
WALLET_ADDRESS=0xYourWalletAddress
PAYPAL_CLIENT_ID=your_paypal_client_id
PAYPAL_CLIENT_SECRET=your_paypal_client_secret
```

- If not set, the SDK will use public endpoints (crypto) or mock mode (PayPal) with low rate limits and show a warning.
- For local/dev/demo, you can skip these, but for real usage, get your free tokens from BlockCypher, CoinGecko, and PayPal.

### Production Usage & Extensibility
- All crypto functions accept an optional `provider` argument for future extensibility (e.g., custom blockchain API, DB, or monitoring service).
- For production, you should:
  - Use persistent storage for payment sessions.
  - Integrate with a real blockchain monitoring provider for payment/session status.
  - Use real fee/signature APIs for fee estimation and signature verification.
  - Handle errors and API rate limits gracefully.
  - Implement health monitoring for all providers and storage backends.
- See function docstrings and TODOs for more details.

See `.env.example` and the README for a template and more details. 

## Stripe Checkout Sessions

You can use the SDK to generate a Stripe-hosted Checkout Session URL for your users. This is useful for web applications where you want to redirect users to Stripe's hosted payment page.

**Example:**

```python
from aiagent_payments.providers import StripeProvider
from aiagent_payments.models import PaymentPlan

stripe_provider = StripeProvider(api_key="sk_test_...")
plan = PaymentPlan(
    id="pro",
    name="Pro Plan",
    description="Premium access",
    payment_type=PaymentType.SUBSCRIPTION,
    price=10.0,
    currency="USD",
)
success_url = "https://yourapp.com/success"
cancel_url = "https://yourapp.com/cancel"
checkout_result = stripe_provider.create_checkout_session(
    user_id="user@example.com",
    plan=plan,
    success_url=success_url,
    cancel_url=cancel_url,
    metadata={"source": "web_checkout"}
)

# Use the checkout_url in your web application
# Redirect user to checkout_url or embed in iframe
checkout_url = checkout_result["url"]
session_id = checkout_result["session_id"]
```

**Note:** For AI agent-driven payments, consider using `process_payment()` instead, which handles payments programmatically without requiring user interaction.

## PayPal Two-Step Payment Flow

PayPal Checkout requires a two-step process: order creation and capture. The SDK provides separate methods for each step to handle user approval properly.

### Step 1: Create Order

```python
from aiagent_payments.providers import PayPalProvider

paypal_provider = PayPalProvider(
    client_id="your_client_id",
    client_secret="your_client_secret",
    sandbox=True  # Use False for production
)

# Create the order
order_response = paypal_provider.create_order(
    user_id="user_123",
    amount=25.99,
    currency="USD",
    return_url="https://yourapp.com/payment/success",
    cancel_url="https://yourapp.com/payment/cancel",
    metadata={"service": "premium_analysis"}
)

# Extract the approval link
approval_link = None
for link in order_response.get('links', []):
    if link.get('rel') == 'approve':
        approval_link = link.get('href')
        break

# Store order_id in your database
order_id = order_response['id']
```

### Step 2: User Approval

Redirect the user to the `approval_link` to approve the payment on PayPal's website.

### Step 3: Capture Order

After user approval, capture the payment:

```python
# Capture the order (call this after user returns to your return_url)
transaction = paypal_provider.capture_order(
    user_id="user_123",
    order_id=order_id,  # From step 1
    metadata={"captured_by": "webhook"}
)

print(f"Payment completed: {transaction.id}")
print(f"Amount: ${transaction.amount} {transaction.currency}")
```

### Webhook Handling

For production applications, handle PayPal webhooks to capture orders automatically:

```python
# In your webhook endpoint
def handle_paypal_webhook(payload, headers):
    # Verify webhook signature
    if paypal_provider.verify_webhook_signature(payload, headers):
        event_type = payload.get('event_type')
        if event_type == 'CHECKOUT.ORDER.APPROVED':
            order_id = payload['resource']['id']
            # Capture the order
            transaction = paypal_provider.capture_order(
                user_id=payload['resource']['custom_id'],
                order_id=order_id
            )
```

**Note:** The `process_payment()` method attempts to create and capture in one step, but this may not work for all PayPal configurations. For production use, always use the two-step flow.

## Stripe Stablecoin Payments

The SDK supports Stripe's stablecoin payment features, allowing you to accept payments in cryptocurrencies like USDC, USDT, DAI, and more.

### Creating a Stablecoin Payment Intent

```python
from aiagent_payments.providers import StripeProvider

stripe_provider = StripeProvider(api_key="sk_test_...")

# Create a payment intent for USDC payment
payment_intent = stripe_provider.create_stablecoin_payment_intent(
    user_id="user@example.com",
    amount=25.00,
    currency="USD",
    stablecoin="usdc",
    metadata={"service": "ai_analysis"}
)

# The client_secret can be used on the frontend to complete the payment
client_secret = payment_intent["client_secret"]
```

### Creating a Stablecoin Checkout Session

For web applications, you can create a hosted checkout session for stablecoin payments:

```python
# Create a stablecoin checkout session (hosted payment page)
checkout_url = stripe_provider.create_stablecoin_checkout_session(
    user_id="user@example.com",
    amount=25.00,
    currency="USD",
    stablecoin="usdc",
    success_url="https://yourapp.com/success",
    cancel_url="https://yourapp.com/cancel",
    metadata={"service": "ai_analysis"}
)

# Redirect user to checkout_url to complete payment
```

### Processing Stablecoin Payments

```python
# Process a stablecoin payment transaction
transaction = stripe_provider.process_stablecoin_payment(
    user_id="user@example.com",
    amount=15.99,
    currency="USD",
    stablecoin="usdt",
    metadata={"service": "content_generation"}
)

print(f"Transaction ID: {transaction.id}")
print(f"Status: {transaction.status}")
```

### Supported Stablecoins

```python
# Get list of supported stablecoins
stablecoins = stripe_provider.get_supported_stablecoins()
print(f"Supported: {stablecoins}")
# Output: ['usdc', 'usdt', 'dai', 'busd', 'gusd']
```

### Verifying Payments

```python
# Verify payment status
is_confirmed = stripe_provider.verify_stablecoin_payment(transaction.id)
if is_confirmed:
    print("Payment confirmed!")
```

### Frontend Integration

To complete the payment on the frontend, use the `client_secret` with Stripe's JavaScript SDK:

```javascript
// Using Stripe.js
const stripe = Stripe('pk_test_...');
const { error } = await stripe.confirmPayment({
  clientSecret: 'pi_..._secret_...',
  confirmParams: {
    return_url: 'https://yourapp.com/success',
  },
});
```

**Benefits of Stripe Stablecoin Payments:**
- Accept multiple stablecoins (USDC, USDT, DAI, BUSD, GUSD)
- Automatic payment method detection
- Secure payment processing via Stripe
- Real-time payment status updates
- Comprehensive error handling
- No need to manage private keys or blockchain infrastructure 

### Stripe Customer Management

Manage customers and subscriptions with Stripe:

```python
from aiagent_payments.providers import StripeProvider

stripe_provider = StripeProvider(api_key="sk_test_...")

# Create a customer
customer = stripe_provider.create_customer(
    user_id="user@example.com",
    email="customer@example.com",
    name="John Doe",
    metadata={"plan": "premium", "source": "web"}
)

print(f"Customer created: {customer['id']}")

# Create customer portal session for subscription management
portal_url = stripe_provider.create_customer_portal_session(
    customer_id=customer["id"],
    return_url="https://yourapp.com/account"
)

# Redirect user to portal_url for billing management
print(f"Portal URL: {portal_url}")
```

**Benefits of Stripe Customer Management:**
- Centralized customer data management
- Self-service subscription management via customer portal
- Automatic billing and payment method updates
- Comprehensive customer analytics and reporting

## USDT ERC-20 Sender Address Requirement

When processing USDT ERC-20 payments, you must provide the Ethereum address the user will send funds from. This address must be included in the `metadata` as `sender_address`:

```python
transaction = provider.process_payment(
    user_id="user123",
    amount=50.0,
    currency="USD",
    metadata={
        "sender_address": "0xabcdef1234567890abcdef1234567890abcdef12",  # REQUIRED
        "description": "AI service payment"
    }
)
```

**Note:** The payment will only be credited if the funds are sent from the exact address provided as `sender_address`. Instruct users to double-check this before sending payment.