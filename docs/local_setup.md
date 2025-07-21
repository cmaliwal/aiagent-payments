# Local Development Setup

## Prerequisites
- Python 3.10+
- Git
- (Optional) Virtualenv or venv

## Clone the Repository
```bash
git clone https://github.com/cmaliwal/aiagent-payments
cd aiagent-payments
```

## Create a Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

## Install Dependencies
```bash
pip install -r requirements.txt
# Optional: for Stripe, PayPal, Crypto, DB, CLI, etc.
pip install stripe paypalrestsdk web3 sqlalchemy alembic flask fastapi uvicorn crewai python-dotenv
```

## Run Tests
```bash
# Run all tests
pytest tests/
# Run only unit tests
pytest tests/unit/
# Run only integration tests
pytest tests/integration/
# Run only functional (CLI) tests
pytest tests/functional/
```

## Run Example
```bash
python examples/basic_usage.py
```

## Lint and Format
```bash
pip install black flake8 isort
black .
flake8 .
isort .
```

## Run CLI
```bash
python cli/main.py --help
```

## Contributing
See [../.github/CONTRIBUTING.md](../.github/CONTRIBUTING.md)

from aiagent_payments.storage import MemoryStorage, FileStorage, DatabaseStorage 

## Enabling/Disabling Storage Backends and Providers

You can control which storage backends and payment providers are available by editing `aiagent_payments/config.py` or setting environment variables:

```python
# In aiagent_payments/config.py
ENABLED_STORAGE = ["memory", "file", "database"]
ENABLED_PROVIDERS = ["mock", "stripe", "paypal", "crypto"]
```

Or via environment variables:

```bash
export AIAgentPayments_EnabledStorage="memory,file,database"
export AIAgentPayments_EnabledProviders="mock,stripe,paypal,crypto"
```

This allows you to go live with only the desired services enabled, without code changes. Only enabled providers/storage are importable and usable; others will raise errors if used.

## API Keys for Providers

For Stripe, PayPal, and Crypto, set your API keys in a `.env` file or as environment variables. See `.env.example` for details. 