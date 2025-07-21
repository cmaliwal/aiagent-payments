# AI Agent Payments SDK

<div align="center">
  <img src="https://raw.githubusercontent.com/cmaliwal/aiagent-payments/main/assets/icon-concept.svg" alt="aiagent_payments Logo" width="128" height="128">
</div>

[![Beta](https://img.shields.io/badge/status-beta-orange)](https://github.com/cmaliwal/aiagent-payments)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support%20the%20author-yellow?logo=buy-me-a-coffee&style=flat-square)](https://coff.ee/chiragmalia)

A plug-and-play Python SDK for monetizing AI and autonomous agents. Easily add subscription, pay-per-use, and access control to your agentic, LLM, or SaaS apps—regardless of framework. Supports modular payment providers (Stripe, PayPal, Crypto, Mock) and pluggable storage (Memory, File, Database) with comprehensive health monitoring and validation.

**Vision:**
- Make payments, access control, and usage tracking easy and robust for AI/agentic apps.
- Provide a modular, extensible foundation for real-world, production-grade monetization.
- Enable rapid prototyping and safe, compliant deployment for both indie hackers and enterprises.

---

## Architecture & Design

- **Modular by Design:** All providers and storage backends are pluggable and can be enabled/disabled via config or environment variables. Only enabled providers/storage are importable and usable; others will raise errors if used.
- **Extensible:** Easy to add new payment providers, storage backends, or custom logic with capability reporting.

For a deep dive into the architecture, design decisions, and vision, see [ARCHITECTURE_DECISION.md](https://github.com/cmaliwal/aiagent-payments/blob/main/ARCHITECTURE_DECISION.md).

---

## Features

- Modular payment providers: Stripe, PayPal, Crypto, Mock
- Pluggable storage: Memory, File, Database
- Subscription, pay-per-use, and freemium models (SDK-managed subscriptions, not Stripe subscriptions)
- CLI for setup, management, and analytics
- Webhook support for Stripe/PayPal
- Stripe Checkout Session support (hosted payment page URL)
- Stripe Stablecoin payments (USDC, USDT, DAI, BUSD, GUSD)
- Stripe Customer Management and Portal access
- PayPal two-step payment flow (create_order → capture_order)
- Usage tracking and analytics
- Comprehensive health monitoring for all components
- Input validation and error handling
- Capability reporting for providers and storage
- Robust logging, validation, and security
- Configurable, code-level enable/disable for providers/storage (see below)
- Comprehensive test suite with mock providers for development
- Open-source friendly and extensible

---

## Quickstart

```python
from aiagent_payments import PaymentManager, PaymentPlan
from aiagent_payments.providers import create_payment_provider, StripeProvider, PayPalProvider, CryptoProvider, MockProvider
from aiagent_payments.storage import MemoryStorage, FileStorage, DatabaseStorage
from aiagent_payments.models import PaymentType, BillingPeriod

# Define a payment plan
plan = PaymentPlan(
    id="pro",
    name="Pro Plan",
    payment_type=PaymentType.SUBSCRIPTION,
    price=10.0,
    currency="USD",
    billing_period=BillingPeriod.MONTHLY,
    features=["premium"],
)

# Setup manager
provider = create_payment_provider("mock")  # or "stripe", "paypal", "crypto"
storage = MemoryStorage()
manager = PaymentManager(storage=storage, payment_provider=provider)
manager.create_payment_plan(plan)

# Subscribe a user (SDK manages subscription internally)
manager.subscribe_user("user@example.com", plan_id="pro")
```

---

## Installation

- **Python:** 3.10+
- **Install:**
  ```bash
  pip install aiagent_payments
  ```
- **Optional extras:**
  - `stripe`, `paypalrestsdk`, `web3`, `sqlalchemy`, `alembic`, `flask`, `fastapi`, `uvicorn`, `crewai`, `python-dotenv`
- See `requirements.txt` and `setup.py` for full list.

---

## Configuration

- Enable/disable providers and storage in `aiagent_payments/config.py`:
  ```python
  ENABLED_STORAGE = ["memory", "file", "database"]
  ENABLED_PROVIDERS = ["mock", "stripe", "paypal", "crypto"]
  ```
- Or override via environment variables:
  ```bash
  export AIAgentPayments_EnabledStorage="memory,file,database"
  export AIAgentPayments_EnabledProviders="mock,stripe,paypal,crypto"
  ```
- Use `.env` for local secrets (see `example.env`).
- **Note:** Only enabled providers/storage are importable and usable; others will raise errors if used.

---

## Usage

### Basic Usage
```python
from aiagent_payments import PaymentManager, PaymentPlan
# ...see Quickstart above...
```

### Advanced Usage
- Multiple users, analytics, file/database storage, error handling.
- See [examples/advanced/advanced_usage.py](https://github.com/cmaliwal/aiagent-payments/blob/main/examples/advanced/advanced_usage.py).

### Health Monitoring

```python
from aiagent_payments.providers import StripeProvider
from aiagent_payments.storage import DatabaseStorage

# Check provider health
stripe_provider = StripeProvider(api_key="sk_test_...")
status = stripe_provider.check_health()
print(f"Provider healthy: {status.is_healthy}")

# Check storage health
storage = DatabaseStorage("payments.db")
status = storage.check_health()
print(f"Storage healthy: {status.is_healthy}")

# Get capabilities
capabilities = stripe_provider.get_capabilities()
print(f"Supports refunds: {capabilities.supports_refunds}")
```

### Input Validation

```python
from aiagent_payments.exceptions import ValidationError

try:
    # This will raise ValidationError for empty user_id
    pm.check_access("", "feature_name")
except ValidationError as e:
    print(f"Validation error: {e}")
```

### CLI Usage
```bash
python cli/main.py --help
```

### Stripe Checkout Sessions
You can generate a Stripe-hosted Checkout Session URL for your users:

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
checkout_url = checkout_result["url"]
session_id = checkout_result["session_id"]
```

### Stripe Stablecoin Payments
Accept cryptocurrency payments using stablecoins like USDC, USDP, and USDG:

```python
from aiagent_payments.providers import StripeProvider

stripe_provider = StripeProvider(api_key="sk_test_...")

# Create a stablecoin payment intent
payment_intent = stripe_provider.create_stablecoin_payment_intent(
    user_id="user@example.com",
    amount=25.00,
    currency="USD",
    stablecoin="usdc",
    metadata={"service": "ai_analysis"}
)

# Create a stablecoin checkout session (hosted payment page)
checkout_url = stripe_provider.create_stablecoin_checkout_session(
    user_id="user@example.com",
    amount=25.00,
    currency="USD",
    stablecoin="usdc",
    success_url="https://yourapp.com/success",
    cancel_url="https://yourapp.com/cancel"
)

# Process the payment
transaction = stripe_provider.process_stablecoin_payment(
    user_id="user@example.com",
    amount=15.99,
    currency="USD",
    stablecoin="usdp"
)

# Get supported stablecoins
stablecoins = stripe_provider.get_supported_stablecoins()
# ['usdc', 'usdp', 'usdg']

# Customer management
customer = stripe_provider.create_customer(
    user_id="user@example.com",
    email="customer@example.com",
    name="John Doe"
)

portal_url = stripe_provider.create_customer_portal_session(
    customer_id=customer["id"],
    return_url="https://yourapp.com/account"
)
```

**Important:** Stripe stablecoin payments are currently only available to a limited set of US businesses. You must:
1. Have a US-based Stripe account
2. Request access to Crypto payment method in your Payment methods settings
3. Wait for Stripe's approval
4. Have the `crypto_payments` capability active

For more details, see [Stripe's stablecoin documentation](https://docs.stripe.com/crypto/stablecoin-payments).

### PayPal Two-Step Payment Flow
PayPal Checkout requires user approval, so the SDK provides a two-step flow:

```python
from aiagent_payments.providers import PayPalProvider

paypal_provider = PayPalProvider(
    client_id="your_client_id",
    client_secret="your_client_secret",
    sandbox=True,
    return_url="https://yourapp.com/return",
    cancel_url="https://yourapp.com/cancel"
)

# Step 1: Create order
order_response = paypal_provider.create_order(
    user_id="user_123",
    amount=25.99,
    currency="USD",
    return_url="https://yourapp.com/success",
    cancel_url="https://yourapp.com/cancel"
)

# Step 2: Get approval link and redirect user
approval_link = next(
    link['href'] for link in order_response['links'] 
    if link['rel'] == 'approve'
)

# Step 3: Capture after user approval (via webhook or return URL)
transaction = paypal_provider.capture_order(
    user_id="user_123",
    order_id=order_response['id']
)
```

---

## Examples

The examples are organized into logical categories and have been curated to ensure they work end-to-end:

### Basic Examples
- [examples/basic/basic_usage.py](https://github.com/cmaliwal/aiagent-payments/blob/main/examples/basic/basic_usage.py): Minimal usage, freemium/pay-per-use with usage limits and subscription models.

### Advanced Examples
- [examples/advanced/advanced_usage.py](https://github.com/cmaliwal/aiagent-payments/blob/main/examples/advanced/advanced_usage.py): Advanced analytics, multiple users, health monitoring, and comprehensive error handling.

### Real-World Examples
- [examples/real_world/usage_based_billing.py](https://github.com/cmaliwal/aiagent-payments/blob/main/examples/real_world/usage_based_billing.py): Usage-based billing with simulation mode and comprehensive analytics.
- [examples/real_world/usage_based_billing_fast.py](https://github.com/cmaliwal/aiagent-payments/blob/main/examples/real_world/usage_based_billing_fast.py): High-volume usage-based billing for SaaS applications.

### Integration Examples
- [examples/integrations/crewai_monetized_example.py](https://github.com/cmaliwal/aiagent-payments/blob/main/examples/integrations/crewai_monetized_example.py): Monetized CrewAI workflow with subscription and pay-per-use models.
- [examples/integrations/petnamegenius_story.py](https://github.com/cmaliwal/aiagent-payments/blob/main/examples/integrations/petnamegenius_story.py): Fun, real-world SaaS story — AI Pet Name Generator with freemium and subscription models.

### LangGraph Examples
- [examples/langgraph/movie_ticket_booking.py](https://github.com/cmaliwal/aiagent-payments/blob/main/examples/langgraph/movie_ticket_booking.py): LangGraph integration for complex agent workflows with payment controls.

All examples are tested and work without external API keys or dependencies. See the [examples directory](https://github.com/cmaliwal/aiagent-payments/tree/main/examples/) for more details.

---

## Documentation

- [Architecture & Design](https://github.com/cmaliwal/aiagent-payments/blob/main/ARCHITECTURE_DECISION.md) — Deep dive into design decisions and architecture
- [Crypto Provider Guide](https://github.com/cmaliwal/aiagent-payments/blob/main/docs/crypto_provider_guide.md) — Complete guide for cryptocurrency payments with limitations and best practices
- [Local Setup](https://github.com/cmaliwal/aiagent-payments/blob/main/docs/local_setup.md) — Development and testing setup
- [Usage Guide](https://github.com/cmaliwal/aiagent-payments/blob/main/docs/usage.md) — Detailed usage examples and patterns

---

## CLI Reference

- `python cli/main.py setup` — Initialize storage and plans
- `python cli/main.py list-plans` — List available payment plans
- `python cli/main.py subscribe --user user@example.com --plan pro` — Subscribe a user
- `python cli/main.py status --user user@example.com` — Show user subscription/status
- See `python cli/main.py --help` for all commands and options

---

## Extending the SDK

- Add new providers: Implement `PaymentProvider` in `aiagent_payments/providers/` with required methods including `_get_capabilities()`, `_validate_configuration()`, and `_perform_health_check()`.
- Add new storage: Implement `StorageBackend` in `aiagent_payments/storage/` with required methods including `_get_capabilities()`, `_validate_configuration()`, and `_perform_health_check()`.
- Register in `__init__.py` and update config as needed.

---

## Testing & Development

- Run all tests:
  ```bash
  pytest --maxfail=3 --disable-warnings -v
  ```
- Lint and format:
  ```bash
  make lint
  make format
  ```
- Contribute: See [CONTRIBUTORS.md](https://github.com/cmaliwal/aiagent-payments/blob/main/CONTRIBUTORS.md)
- CI/CD runs on Python 3.12.

---

## Compliance & Legal

- **Disclaimer:** This SDK is provided as-is, with no warranty. You are responsible for compliance with all laws and payment provider terms (including Stripe, PayPal, and crypto APIs). You must supply your own API keys for production use of Stripe, PayPal, and Crypto providers.
- Fallback/mock modes are for dev/test only and log warnings in production.
- See [DISCLAIMER.md](https://github.com/cmaliwal/aiagent-payments/blob/main/DISCLAIMER.md) for full details.

---

## Roadmap & Limitations

- See "Known Limitations and Roadmap" in this repo for planned features and current limitations.
- Contributions welcome! See TODOs in code and open issues.

---

## Get Involved

We welcome contributions, bug reports, and feedback from the AI agent developer community. Open an issue or pull request, or join the discussion to help shape the future of agent monetization.
