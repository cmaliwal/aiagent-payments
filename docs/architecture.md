# AI Agent Payments SDK Architecture

## System Architecture

```mermaid
flowchart TD
  A[User] -->|Visits AI Agent Service| B[Frontend/API]
  B -->|Requests Feature| C[AI Agent SDK Layer]
  C -->|Check Access/Quota| D[PaymentManager]
  D -->|Check Subscription/Usage| E[Storage Backend]
  D -->|Process Payment| F[Payment Provider]
  F -->|Verify Payment| G[External Payment Gateway]
  E -->|Return Usage/Subscription| D
  D -->|Allow or Deny| C
  C -->|Respond| B
  B -->|Show Result/Error| A

  subgraph SDK
    D
    E
    F
    H[Health Monitor]
    I[Capability Manager]
  end

  subgraph External
    G
  end

  E -->|Health Check| H
  F -->|Health Check| H
  E -->|Capabilities| I
  F -->|Capabilities| I
```

**Explanation:**
- **User** interacts with your AI agent via a frontend or API.
- **Frontend/API** sends feature requests to the SDK layer.
- **AI Agent SDK Layer** (your code + SDK) checks access, quota, and payment status.
- **PaymentManager** coordinates access control, usage, and payment logic with enhanced validation.
- **Storage Backend** (memory, file, or database) stores plans, subscriptions, and usage. Only enabled storage backends are available.
- **Payment Provider** (Stripe, PayPal, Crypto, etc.) processes payments. Only enabled providers are available.
- **Health Monitor** provides real-time health status for all components.
- **Capability Manager** reports supported features for each component.
- **External Payment Gateway** is the actual payment network (Stripe, PayPal, blockchain, etc.).

---

## Enhanced Component Design

### Payment Provider Architecture

```mermaid
classDiagram
    class PaymentProvider {
        <<abstract>>
        +name: str
        +capabilities: ProviderCapabilities
        +status: ProviderStatus
        +check_health() ProviderStatus
        +get_capabilities() ProviderCapabilities
        +get_provider_info() dict
        +process_payment() PaymentTransaction
        +verify_payment() bool
        +refund_payment() Any
        +get_payment_status() str
    }
    
    class ProviderCapabilities {
        +supports_refunds: bool
        +supports_webhooks: bool
        +supports_partial_refunds: bool
        +supports_subscriptions: bool
        +supports_metadata: bool
        +supported_currencies: List[str]
        +min_amount: float
        +max_amount: float
        +processing_time_seconds: float
    }
    
    class ProviderStatus {
        +is_healthy: bool
        +last_check: datetime
        +error_message: str
        +response_time_ms: float
    }
    
    PaymentProvider --> ProviderCapabilities
    PaymentProvider --> ProviderStatus
```

### Storage Backend Architecture

```mermaid
classDiagram
    class StorageBackend {
        <<abstract>>
        +name: str
        +capabilities: StorageCapabilities
        +status: StorageStatus
        +check_health() StorageStatus
        +get_capabilities() StorageCapabilities
        +get_storage_info() dict
        +save_payment_plan() void
        +get_payment_plan() PaymentPlan
        +list_payment_plans() List[PaymentPlan]
        +save_subscription() void
        +get_subscription() Subscription
        +get_user_subscription() Subscription
        +save_usage_record() void
        +get_user_usage() List[UsageRecord]
        +save_transaction() void
        +get_transaction() PaymentTransaction
    }
    
    class StorageCapabilities {
        +supports_transactions: bool
        +supports_encryption: bool
        +supports_backup: bool
        +supports_search: bool
        +supports_indexing: bool
        +max_data_size: int
        +supports_concurrent_access: bool
        +supports_pagination: bool
        +supports_bulk_operations: bool
    }
    
    class StorageStatus {
        +is_healthy: bool
        +last_check: datetime
        +error_message: str
        +response_time_ms: float
    }
    
    StorageBackend --> StorageCapabilities
    StorageBackend --> StorageStatus
```

---

## User Journey

```mermaid
journey
  title User Journey: Monetized AI Agent
  section Onboarding
    User visits service: 5: User
    User views pricing/plans: 4: User
    User signs up: 5: User
  section Subscription/Payment
    User selects plan: 4: User
    User enters payment: 3: User
    Payment processed: 3: Payment Provider
    Subscription activated: 5: SDK
  section Usage
    User requests feature: 5: User
    SDK validates input: 4: SDK
    SDK checks access/quota: 4: SDK
    If allowed, feature executed: 5: SDK
    If not, prompt for upgrade/payment: 2: SDK
  section Renewal/Upgrade
    User receives renewal reminder: 3: SDK
    User upgrades/cancels: 4: User
    Payment processed: 3: Payment Provider
    Subscription updated: 5: SDK
  section Health Monitoring
    System monitors provider health: 4: System
    System monitors storage health: 4: System
    Alerts on component failures: 3: System
```

**Explanation:**
- **Onboarding:** User discovers your service, reviews plans, and signs up.
- **Subscription/Payment:** User selects a plan, enters payment, and the SDK activates their subscription after payment is processed.
- **Usage:** User requests features; SDK validates input, checks access/quota and either allows usage or prompts for upgrade/payment.
- **Renewal/Upgrade:** SDK reminds user to renew; user can upgrade/cancel; payment is processed and subscription is updated.
- **Health Monitoring:** System continuously monitors the health of all components and alerts on failures.
- **Compliance:** If a disabled provider/storage is selected, the SDK will raise an error and log a warning. Only enabled providers/storage are importable and usable; others will raise errors if used.

---

## Configuration Management

The SDK uses a robust configuration system that allows fine-grained control over which components are available:

```python
# Configuration can be set via environment variables
export AIAgentPayments_EnabledStorage="memory,file,database"
export AIAgentPayments_EnabledProviders="mock,stripe,paypal,crypto"

# Or via code
from aiagent_payments.config import ENABLED_STORAGE, ENABLED_PROVIDERS
ENABLED_STORAGE = ["memory", "file", "database"]
ENABLED_PROVIDERS = ["mock", "stripe", "paypal", "crypto"]
```

This ensures that:
- Only enabled components are importable
- Disabled components raise clear errors if accessed
- Configuration is validated at startup
- Production deployments can restrict functionality as needed

---

## Error Handling and Validation

The SDK implements comprehensive error handling and validation:

### Exception Hierarchy

```mermaid
classDiagram
    class AIAgentPaymentsError {
        <<abstract>>
        +message: str
        +code: str
        +details: dict
    }
    
    class PaymentError {
        <<abstract>>
        +transaction_id: str
        +provider: str
    }
    
    class PaymentFailed {
        +transaction_id: str
        +provider: str
    }
    
    class PaymentRequired {
        +feature: str
        +required_amount: float
    }
    
    class UsageLimitExceeded {
        +feature: str
        +current_usage: int
        +limit: int
    }
    
    class ValidationError {
        +field: str
        +value: Any
    }
    
    class ProviderError {
        +provider: str
        +operation: str
    }
    
    class StorageError {
        +storage_type: str
        +operation: str
        +entity_id: str
    }
    
    AIAgentPaymentsError <|-- PaymentError
    AIAgentPaymentsError <|-- ValidationError
    AIAgentPaymentsError <|-- ProviderError
    AIAgentPaymentsError <|-- StorageError
    PaymentError <|-- PaymentFailed
    PaymentError <|-- PaymentRequired
    AIAgentPaymentsError <|-- UsageLimitExceeded
```

### Input Validation

All public methods now include comprehensive input validation:
- Empty or invalid user IDs
- Empty or invalid feature names
- Invalid payment amounts
- Invalid currency codes
- Invalid configuration parameters

### Health Monitoring

Each component provides health monitoring capabilities:
- **Payment Providers:** Check API connectivity, response times, and account status
- **Storage Backends:** Check data integrity, connection status, and performance
- **Automatic Monitoring:** Components can be monitored continuously for production deployments

---

## Performance and Scalability

### Caching and Optimization

- **Memory Storage:** Fast in-memory operations for development and testing
- **File Storage:** Efficient JSON-based storage with lazy loading
- **Database Storage:** Optimized SQLite with indexing and transaction support

### Concurrent Access

- **Thread Safety:** Storage backends support concurrent access where possible
- **Connection Pooling:** Database storage uses connection pooling for efficiency
- **Atomic Operations:** Critical operations use transactions where supported

### Monitoring and Observability

- **Structured Logging:** All operations are logged with structured data
- **Performance Metrics:** Response times and throughput are tracked
- **Health Checks:** Real-time health status for all components
- **Error Tracking:** Comprehensive error reporting with context 

- For USDT ERC-20 payments, the system requires the user to provide the sender's Ethereum address (sender_address) in the payment metadata. Payments are only credited if the funds are sent from this address. 