# Installation Guide

This guide provides detailed installation instructions for AIAgent Payments, covering different environments, dependencies, and configuration options.

## 📋 System Requirements

### Minimum Requirements
- **Python**: 3.8 or higher
- **pip**: Latest version
- **Memory**: 512MB RAM
- **Storage**: 100MB free space

### Recommended Requirements
- **Python**: 3.10 or higher
- **Memory**: 1GB RAM
- **Storage**: 500MB free space
- **Network**: Stable internet connection for payment provider APIs

## 🚀 Installation Methods

### Method 1: pip Installation (Recommended)

```bash
# Install the latest version
pip install aiagent-payments

# Install with specific version
pip install aiagent-payments==0.0.1

# Install with extra dependencies
pip install aiagent-payments[stripe,paypal,crypto]
```

### Method 2: Source Installation

```bash
# Clone the repository
git clone https://github.com/cmaliwal/aiagent-payments.git
cd aiagent-payments

# Install in development mode
pip install -e .

# Install with all dependencies
pip install -e ".[all]"
```

### Method 3: Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv aiagent_env

# Activate virtual environment
# On Windows:
aiagent_env\Scripts\activate
# On macOS/Linux:
source aiagent_env/bin/activate

# Install the package
pip install aiagent-payments
```

## 📦 Dependency Management

### Core Dependencies

The package automatically installs these core dependencies:

```python
# Core requirements
requests>=2.25.0
pydantic>=1.8.0
python-dotenv>=0.19.0
```

### Optional Dependencies

Install specific provider dependencies as needed:

```bash
# Stripe support
pip install aiagent-payments[stripe]
# Includes: stripe>=5.0.0

# PayPal support
pip install aiagent-payments[paypal]
# Includes: paypalrestsdk>=1.13.0

# Cryptocurrency support
pip install aiagent-payments[crypto]
# Includes: web3>=5.0.0, eth-account>=0.5.0

# Database support
pip install aiagent-payments[database]
# Includes: sqlalchemy>=1.4.0, alembic>=1.7.0

# Web framework support
pip install aiagent-payments[web]
# Includes: flask>=2.0.0, fastapi>=0.68.0

# All dependencies
pip install aiagent-payments[all]
```

## 🔧 Configuration Setup

### Environment Variables

Create a `.env` file in your project root:

```bash
# Payment Provider Configuration
STRIPE_SECRET_KEY=sk_test_your_stripe_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_key
PAYPAL_CLIENT_ID=your_paypal_client_id
PAYPAL_CLIENT_SECRET=your_paypal_client_secret

# Database Configuration (optional)
DATABASE_URL=sqlite:///payments.db
DATABASE_URL=postgresql://user:pass@localhost/payments

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=payments.log

# Security Configuration
SECRET_KEY=your_secret_key_here
WEBHOOK_SECRET=your_webhook_secret

# Feature Flags
ENABLE_CRYPTO=true
ENABLE_WEBHOOKS=true
SANDBOX_MODE=true
```

### Configuration File

Create a `config.py` file for programmatic configuration:

```python
from aiagent_payments.config import PaymentConfig

config = PaymentConfig(
    # Provider settings
    stripe_secret_key="sk_test_...",
    paypal_client_id="your_client_id",
    
    # Storage settings
    storage_type="memory",  # or "file", "database"
    database_url="sqlite:///payments.db",
    
    # Security settings
    secret_key="your_secret_key",
    webhook_secret="your_webhook_secret",
    
    # Feature flags
    enable_crypto=True,
    enable_webhooks=True,
    sandbox_mode=True,
    
    # Logging
    log_level="INFO",
    log_file="payments.log"
)
```

## 🗄️ Storage Backend Setup

### Memory Storage (Default)

```python
from aiagent_payments.storage import MemoryStorage

# Simple in-memory storage (data lost on restart)
storage = MemoryStorage()
```

### File Storage

```python
from aiagent_payments.storage import FileStorage

# Persistent file-based storage
storage = FileStorage(
    data_dir="./payments_data",
    backup_enabled=True
)
```

### Database Storage

```python
from aiagent_payments.storage import DatabaseStorage

# SQLite database
storage = DatabaseStorage(
    database_url="sqlite:///payments.db"
)

# PostgreSQL database
storage = DatabaseStorage(
    database_url="postgresql://user:pass@localhost/payments"
)

# MySQL database
storage = DatabaseStorage(
    database_url="mysql://user:pass@localhost/payments"
)
```

## 🔐 Security Configuration

### API Key Management

```python
import os
from aiagent_payments import PaymentProcessor

# Use environment variables (recommended)
processor = PaymentProcessor(
    provider="stripe",
    api_key=os.getenv("STRIPE_SECRET_KEY")
)

# Use configuration file
from aiagent_payments.config import load_config
config = load_config("config.yaml")
processor = PaymentProcessor(
    provider="stripe",
    api_key=config.stripe.secret_key
)
```

### Webhook Security

```python
# Verify webhook signatures
@app.route('/webhook', methods=['POST'])
def handle_webhook():
    signature = request.headers.get('Stripe-Signature')
    
    if not processor.verify_webhook(request.data, signature):
        return {'error': 'Invalid signature'}, 400
    
    # Process webhook
    event = processor.parse_webhook(request.data)
    return {'status': 'success'}, 200
```

## 🧪 Testing Setup

### Install Test Dependencies

```bash
# Install test dependencies
pip install -r dev-requirements.txt

# Or install with test extras
pip install aiagent-payments[test]
```

### Run Tests

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=aiagent_payments

# Run specific test categories
python -m pytest tests/unit/
python -m pytest tests/integration/
python -m pytest tests/functional/
```

### Test Configuration

```python
# test_config.py
import pytest
from aiagent_payments import PaymentProcessor

@pytest.fixture
def mock_processor():
    return PaymentProcessor(provider="mock")

@pytest.fixture
def stripe_processor():
    return PaymentProcessor(
        provider="stripe",
        api_key="sk_test_..."
    )
```

## 🐳 Docker Installation

### Dockerfile

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run application
CMD ["python", "app.py"]
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  aiagent-payments:
    build: .
    ports:
      - "8000:8000"
    environment:
      - STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY}
      - DATABASE_URL=${DATABASE_URL}
    volumes:
      - ./data:/app/data
    depends_on:
      - postgres

  postgres:
    image: postgres:13
    environment:
      - POSTGRES_DB=payments
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

## 🔄 Development Setup

### Clone and Setup

```bash
# Clone repository
git clone https://github.com/cmaliwal/aiagent-payments.git
cd aiagent-payments

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Development Dependencies

```bash
# Install development dependencies
pip install -r dev-requirements.txt

# Install linting and formatting tools
pip install black isort flake8 mypy

# Install testing tools
pip install pytest pytest-cov pytest-mock
```

### Code Quality Tools

```bash
# Format code
make format

# Lint code
make lint

# Run type checking
make type-check

# Run tests
make test
```

## 🌐 Web Framework Integration

### Flask Integration

```python
from flask import Flask, request, jsonify
from aiagent_payments import PaymentProcessor

app = Flask(__name__)
processor = PaymentProcessor(provider="stripe")

@app.route('/payment', methods=['POST'])
def create_payment():
    data = request.get_json()
    
    result = processor.process_payment(
        amount=data['amount'],
        currency=data['currency'],
        description=data['description']
    )
    
    return jsonify({
        'payment_id': result.payment_id,
        'status': result.status
    })

if __name__ == '__main__':
    app.run(debug=True)
```

### FastAPI Integration

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from aiagent_payments import PaymentProcessor

app = FastAPI()
processor = PaymentProcessor(provider="stripe")

class PaymentRequest(BaseModel):
    amount: int
    currency: str
    description: str

@app.post("/payment")
async def create_payment(payment: PaymentRequest):
    try:
        result = processor.process_payment(
            amount=payment.amount,
            currency=payment.currency,
            description=payment.description
        )
        
        return {
            'payment_id': result.payment_id,
            'status': result.status
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### Django Integration

```python
# settings.py
INSTALLED_APPS = [
    # ... other apps
    'aiagent_payments',
]

# Payment configuration
PAYMENT_CONFIG = {
    'provider': 'stripe',
    'api_key': os.getenv('STRIPE_SECRET_KEY'),
    'storage_type': 'database',
    'database_url': os.getenv('DATABASE_URL'),
}

# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from aiagent_payments import PaymentProcessor

processor = PaymentProcessor(provider="stripe")

@csrf_exempt
def create_payment(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        
        result = processor.process_payment(
            amount=data['amount'],
            currency=data['currency'],
            description=data['description']
        )
        
        return JsonResponse({
            'payment_id': result.payment_id,
            'status': result.status
        })
```

## 🔍 Verification

### Test Installation

```python
# test_installation.py
from aiagent_payments import PaymentProcessor

def test_installation():
    # Test basic import
    processor = PaymentProcessor(provider="mock")
    
    # Test payment processing
    result = processor.process_payment(
        amount=1000,
        currency="usd",
        description="Test payment"
    )
    
    print(f"✅ Installation successful!")
    print(f"Payment ID: {result.payment_id}")
    print(f"Status: {result.status}")

if __name__ == "__main__":
    test_installation()
```

### Health Check

```python
# health_check.py
from aiagent_payments import PaymentProcessor
import os

def health_check():
    # Check environment variables
    required_vars = ['STRIPE_SECRET_KEY', 'PAYPAL_CLIENT_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"⚠️  Missing environment variables: {missing_vars}")
    else:
        print("✅ Environment variables configured")
    
    # Test provider connectivity
    try:
        processor = PaymentProcessor(provider="stripe")
        print("✅ Stripe provider configured")
    except Exception as e:
        print(f"❌ Stripe provider error: {e}")
    
    # Test storage
    try:
        from aiagent_payments.storage import MemoryStorage
        storage = MemoryStorage()
        print("✅ Storage backend working")
    except Exception as e:
        print(f"❌ Storage error: {e}")

if __name__ == "__main__":
    health_check()
```

## 🚨 Troubleshooting

### Common Installation Issues

#### 1. Python Version Issues

```bash
# Check Python version
python --version

# If version is too old, upgrade Python
# On macOS with Homebrew:
brew install python@3.10

# On Ubuntu:
sudo apt update
sudo apt install python3.10
```

#### 2. Permission Issues

```bash
# Install with user permissions
pip install --user aiagent-payments

# Or use virtual environment
python -m venv venv
source venv/bin/activate
pip install aiagent-payments
```

#### 3. Dependency Conflicts

```bash
# Check for conflicts
pip check

# Install with --force-reinstall
pip install --force-reinstall aiagent-payments

# Or use pip-tools
pip install pip-tools
pip-compile requirements.in
pip-sync
```

#### 4. Network Issues

```bash
# Use alternative package index
pip install -i https://pypi.org/simple/ aiagent-payments

# Or use conda
conda install -c conda-forge aiagent-payments
```

## 📚 Next Steps

After successful installation:

1. **Configure your payment providers** - Set up Stripe, PayPal, or other providers
2. **Set up storage backend** - Choose memory, file, or database storage
3. **Test the integration** - Run the verification scripts
4. **Read the documentation** - Check out the [Getting Started](Getting-Started) guide
5. **Explore examples** - Look at the `/examples` directory

## 🆘 Need Help?

- **Installation Issues**: Check the [Common Errors](Common-Errors) page
- **Configuration Problems**: Review the configuration examples above
- **GitHub Issues**: Report bugs and request features
- **Discussions**: Ask questions in GitHub Discussions

---

**Happy installing! 🚀** 