# Common Errors & Troubleshooting

This guide helps you resolve common issues and errors when using AIAgent Payments. Each error includes the cause, solution, and prevention tips.

## 🚨 Payment Processing Errors

### 1. Invalid API Key

**Error Message:**
```
Invalid API key provided
```

**Cause:**
- Incorrect or expired API key
- Using test key in production or vice versa
- API key not properly configured

**Solution:**
```python
# Check your API key format
# Stripe test keys start with: sk_test_
# Stripe live keys start with: sk_live_

import os
from aiagent_payments import PaymentProcessor

# Verify environment variable is set
print(f"API Key: {os.getenv('STRIPE_SECRET_KEY')[:10]}...")

# Initialize with explicit key
processor = PaymentProcessor(
    provider="stripe",
    api_key="sk_test_your_actual_key_here"
)
```

**Prevention:**
- Use environment variables for API keys
- Never commit API keys to version control
- Regularly rotate API keys
- Use test keys for development

### 2. Insufficient Funds

**Error Message:**
```
Your card was declined
```

**Cause:**
- Card has insufficient funds
- Card limit exceeded
- Bank declined the transaction

**Solution:**
```python
from aiagent_payments.exceptions import PaymentError

try:
    result = processor.process_payment(
        amount=1000,
        currency="usd",
        description="Test payment"
    )
except PaymentError as e:
    if "insufficient_funds" in str(e):
        print("Card has insufficient funds")
        # Ask user to use a different payment method
    elif "card_declined" in str(e):
        print("Card was declined by bank")
        # Suggest contacting bank
```

**Prevention:**
- Use test cards for development
- Implement proper error handling
- Provide clear error messages to users

### 3. Invalid Currency

**Error Message:**
```
Currency not supported
```

**Cause:**
- Currency code not supported by payment provider
- Currency not enabled in your account
- Incorrect currency format

**Solution:**
```python
# Check supported currencies
supported_currencies = ["usd", "eur", "gbp", "cad", "aud"]

currency = "usd"  # Use lowercase
if currency.lower() not in supported_currencies:
    print(f"Currency {currency} not supported")

# Process payment with valid currency
result = processor.process_payment(
    amount=1000,
    currency="usd",  # Use supported currency
    description="Test payment"
)
```

**Prevention:**
- Validate currency before processing
- Use lowercase currency codes
- Check provider documentation for supported currencies

### 4. Invalid Amount

**Error Message:**
```
Invalid amount
```

**Cause:**
- Amount is zero or negative
- Amount exceeds provider limits
- Amount format is incorrect

**Solution:**
```python
# Validate amount before processing
def validate_amount(amount, currency):
    if amount <= 0:
        raise ValueError("Amount must be positive")
    
    # Check minimum amount (varies by currency)
    min_amounts = {"usd": 50, "eur": 50, "gbp": 30}  # in cents
    if amount < min_amounts.get(currency.lower(), 50):
        raise ValueError(f"Amount too small for {currency}")
    
    # Check maximum amount
    if amount > 999999:  # $9,999.99
        raise ValueError("Amount too large")
    
    return amount

# Use validated amount
valid_amount = validate_amount(1000, "usd")
result = processor.process_payment(
    amount=valid_amount,
    currency="usd",
    description="Test payment"
)
```

**Prevention:**
- Always validate amounts before processing
- Use amounts in cents (smallest currency unit)
- Implement amount limits

## 🔧 Configuration Errors

### 5. Missing Environment Variables

**Error Message:**
```
Environment variable STRIPE_SECRET_KEY not found
```

**Cause:**
- Environment variable not set
- Incorrect variable name
- .env file not loaded

**Solution:**
```python
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Check if variables are set
required_vars = ["STRIPE_SECRET_KEY", "PAYPAL_CLIENT_ID"]
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    print(f"Missing environment variables: {missing_vars}")
    print("Please set them in your .env file or environment")

# Set fallback values for development
if not os.getenv("STRIPE_SECRET_KEY"):
    os.environ["STRIPE_SECRET_KEY"] = "sk_test_placeholder"
```

**Prevention:**
- Use a .env file for local development
- Document required environment variables
- Use environment variable validation

### 6. PayPal Provider Configuration Errors

#### 6.1 "return_url cannot be empty" Error

**Error Message:**
```
ValidationError: return_url cannot be empty
```

**Cause:**
- Using the factory function without passing `return_url` and `cancel_url` parameters
- Parameters not being forwarded correctly to the PayPal provider (fixed in latest version)

**Solution:**
```python
from aiagent_payments.providers import create_payment_provider

# ✅ Correct way (using factory function)
provider = create_payment_provider(
    "paypal",
    client_id="your_client_id",
    client_secret="your_client_secret",
    return_url="https://yourapp.com/success",  # Required
    cancel_url="https://yourapp.com/cancel"    # Required
)

# ✅ Alternative: Direct initialization
from aiagent_payments.providers import PayPalProvider
provider = PayPalProvider(
    client_id="your_client_id",
    client_secret="your_client_secret",
    return_url="https://yourapp.com/success",
    cancel_url="https://yourapp.com/cancel"
)

# ❌ Wrong way (will cause error)
provider = create_payment_provider(
    "paypal",
    client_id="your_client_id",
    client_secret="your_client_secret"
    # Missing return_url and cancel_url
)
```

**Prevention:**
- Always provide `return_url` and `cancel_url` when using PayPal
- Use environment variables for URLs
- Test configuration in sandbox mode first

#### 6.2 PayPal API "Unprocessable Request" Error

**Error Message:**
```
PayPal request unprocessable. Check request format.
```

**Cause:**
- PayPal sandbox account configuration issues
- Missing API permissions
- Test account restrictions
- Order capture attempted before user approval

**Solution:**
```python
# Use two-step flow instead of direct capture
# Step 1: Create order
order_response = provider.create_order(
    user_id="user_123",
    amount=25.99,
    currency="USD",
    return_url="https://yourapp.com/success",
    cancel_url="https://yourapp.com/cancel"
)

# Step 2: Get approval URL and redirect user
approval_url = None
for link in order_response.get("links", []):
    if link.get("rel") == "approve":
        approval_url = link.get("href")
        break

# Step 3: Capture only after user approval (via webhook or return)
# Don't capture immediately in process_payment()
```

**Prevention:**
- Use sandbox accounts for testing
- Implement proper two-step payment flow
- Handle webhooks for order approval events

### 7. Invalid Provider Configuration

**Error Message:**
```
Invalid payment provider: unknown_provider
```

**Cause:**
- Provider name misspelled
- Provider not installed
- Provider not supported

**Solution:**
```python
# Check available providers
from aiagent_payments.providers import get_available_providers

available_providers = get_available_providers()
print(f"Available providers: {available_providers}")

# Use correct provider name
processor = PaymentProcessor(
    provider="stripe",  # Use exact provider name
    api_key="sk_test_..."
)
```

**Prevention:**
- Use exact provider names
- Install required dependencies
- Check provider documentation

### 8. Crypto Provider Storage Error

**Error Message:**
```
In-memory storage not allowed in production mode. Transaction data must be persisted.
```

**Cause:**
- Using `MemoryStorage` in production mode
- Missing `AIAgentPayments_DevMode` environment variable

**Solution:**
```python
# For development/testing
import os
os.environ["AIAgentPayments_DevMode"] = "1"

# For production, use persistent storage
from aiagent_payments.storage import DatabaseStorage, FileStorage

# Use database storage
storage = DatabaseStorage(database_url="sqlite:///payments.db")

# Or use file storage
storage = FileStorage(data_dir="./payments_data")

# Initialize provider with persistent storage
provider = create_payment_provider(
    "crypto",
    wallet_address="0x...",
    infura_project_id="your_project_id",
    storage=storage
)
```

**Prevention:**
- Set `AIAgentPayments_DevMode=1` for development
- Use persistent storage in production
- Configure proper storage backends

## 🌐 Webhook Errors

### 9. Invalid Webhook Signature

**Error Message:**
```
Invalid webhook signature
```

**Cause:**
- Incorrect webhook secret
- Webhook payload tampered
- Wrong signature verification method

**Solution:**
```python
from flask import Flask, request

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    signature = request.headers.get('Stripe-Signature')
    
    if not signature:
        return {'error': 'No signature provided'}, 400
    
    try:
        # Verify webhook signature
        event = processor.verify_webhook(
            payload=request.data,
            signature=signature
        )
    except Exception as e:
        print(f"Webhook verification failed: {e}")
        return {'error': 'Invalid signature'}, 400
    
    # Process the event
    return {'status': 'success'}, 200
```

**Prevention:**
- Store webhook secrets securely
- Always verify webhook signatures
- Use HTTPS for webhook endpoints

### 10. Webhook Timeout

**Error Message:**
```
Webhook timeout
```

**Cause:**
- Webhook processing takes too long
- Network issues
- Server overload

**Solution:**
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    # Process webhook asynchronously
    def process_webhook():
        # Your webhook processing logic
        pass
    
    # Run in background thread
    with ThreadPoolExecutor() as executor:
        executor.submit(process_webhook)
    
    # Return immediately
    return {'status': 'accepted'}, 202
```

**Prevention:**
- Process webhooks asynchronously
- Keep webhook handlers lightweight
- Implement proper error handling

## 💾 Storage Errors

### 11. Database Connection Error

**Error Message:**
```
Database connection failed
```

**Cause:**
- Database server down
- Incorrect connection string
- Network issues

**Solution:**
```python
from aiagent_payments.storage import DatabaseStorage

# Test database connection
def test_database_connection():
    try:
        storage = DatabaseStorage(
            database_url="postgresql://user:pass@localhost/payments"
        )
        # Test connection
        storage.health_check()
        print("Database connection successful")
    except Exception as e:
        print(f"Database connection failed: {e}")
        # Fallback to file storage
        return FileStorage(data_dir="./payments_data")

# Use fallback storage
storage = test_database_connection()
```

**Prevention:**
- Implement connection pooling
- Use connection retry logic
- Have fallback storage options

### 12. File Storage Permission Error

**Error Message:**
```
Permission denied
```

**Cause:**
- Insufficient file permissions
- Directory doesn't exist
- Disk space full

**Solution:**
```python
import os
from aiagent_payments.storage import FileStorage

# Check and create directory
def setup_file_storage():
    data_dir = "./payments_data"
    
    # Create directory if it doesn't exist
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, mode=0o755)
    
    # Check permissions
    if not os.access(data_dir, os.W_OK):
        print(f"No write permission for {data_dir}")
        # Use memory storage as fallback
        return MemoryStorage()
    
    return FileStorage(data_dir=data_dir)

storage = setup_file_storage()
```

**Prevention:**
- Set proper file permissions
- Monitor disk space
- Use absolute paths

## 🔐 Security Errors

### 13. SSL Certificate Error

**Error Message:**
```
SSL certificate verification failed
```

**Cause:**
- Invalid SSL certificate
- Self-signed certificate
- Certificate expired

**Solution:**
```python
import ssl
import requests

# For development only - disable SSL verification
# WARNING: Never use this in production
requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.verify = False

# Configure provider with custom session
provider = create_payment_provider(
    "stripe",
    api_key="sk_test_...",
    session=session
)
```

**Prevention:**
- Use valid SSL certificates
- Keep certificates updated
- Never disable SSL in production

## 🔧 Recent Fixes & Updates

### PayPal Provider Factory Fix

**Issue:** The `create_payment_provider` factory function was not forwarding `return_url`, `cancel_url`, `webhook_id`, and `timeout` parameters to the PayPal provider constructor.

**Fix:** Updated the factory function to properly forward all configuration parameters.

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

## 📚 Additional Resources

- [PayPal Integration Guide](PayPal-Integration.md)
- [Getting Started Guide](Getting-Started.md)
- [Installation Guide](Installation-Guide.md)
- [GitHub Issues](https://github.com/cmaliwal/aiagent-payments/issues)

## 🆘 Still Need Help?

If you're still experiencing issues:

1. **Check the logs** for detailed error messages
2. **Verify your configuration** using the examples above
3. **Test in sandbox mode** before going to production
4. **Open an issue** on GitHub with:
   - Error message and stack trace
   - Your configuration (without sensitive data)
   - Steps to reproduce the issue
   - Environment details (Python version, OS, etc.)

---

**Remember:** Always test your payment integration thoroughly in sandbox/test mode before deploying to production! 