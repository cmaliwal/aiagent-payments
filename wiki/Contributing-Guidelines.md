# Contributing Guidelines

Thank you for your interest in contributing to AIAgent Payments! This guide will help you get started with contributing to the project.

## 🤝 How to Contribute

We welcome contributions from the community! Here are the main ways you can contribute:

- **🐛 Bug Reports**: Report bugs and issues
- **💡 Feature Requests**: Suggest new features and improvements
- **📝 Documentation**: Improve documentation and examples
- **🔧 Code Contributions**: Submit pull requests with code changes
- **🧪 Testing**: Help test features and report issues
- **💬 Community Support**: Help other users in discussions

## 📋 Before You Start

### Prerequisites

- **Python 3.8+** (we recommend 3.10+)
- **Git** for version control
- **GitHub account** for submitting contributions
- **Basic knowledge** of Python and payment processing

### Development Setup

1. **Fork the repository**
   ```bash
   # Fork on GitHub, then clone your fork
   git clone https://github.com/YOUR_USERNAME/aiagent-payments.git
   cd aiagent-payments
   ```

2. **Set up development environment**
   ```bash
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install in development mode
   pip install -e ".[dev]"
   
   # Install pre-commit hooks
   pre-commit install
   ```

3. **Verify setup**
   ```bash
   # Run tests to ensure everything works
   python -m pytest
   
   # Run linting
   make lint
   
   # Run formatting
   make format
   ```

## 🐛 Reporting Bugs

### Before Reporting

1. **Check existing issues** - Search for similar issues
2. **Test with latest version** - Ensure you're using the latest release
3. **Reproduce the issue** - Make sure you can consistently reproduce it
4. **Check documentation** - Verify it's not a configuration issue

### Bug Report Template

```markdown
**Bug Description**
A clear description of what the bug is.

**Steps to Reproduce**
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

**Expected Behavior**
What you expected to happen.

**Actual Behavior**
What actually happened.

**Environment**
- Python version: [e.g., 3.10.0]
- AIAgent Payments version: [e.g., 0.0.1-beta]
- OS: [e.g., macOS 12.0]
- Payment provider: [e.g., Stripe, PayPal]

**Error Messages**
```
Paste any error messages here
```

**Additional Context**
Any other context about the problem.
```

## 💡 Requesting Features

### Feature Request Template

```markdown
**Feature Description**
A clear description of the feature you'd like to see.

**Use Case**
How would this feature be used? What problem does it solve?

**Proposed Solution**
If you have ideas for implementation, describe them here.

**Alternatives Considered**
Any alternative solutions you've considered.

**Additional Context**
Any other context, screenshots, or examples.
```

## 🔧 Code Contributions

### Development Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write code following our style guidelines
   - Add tests for new functionality
   - Update documentation if needed

3. **Test your changes**
   ```bash
   # Run all tests
   python -m pytest
   
   # Run specific tests
   python -m pytest tests/unit/test_your_feature.py
   
   # Run with coverage
   python -m pytest --cov=aiagent_payments
   ```

4. **Check code quality**
   ```bash
   # Format code
   make format
   
   # Lint code
   make lint
   
   # Type checking
   make type-check
   ```

5. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add new payment provider support"
   ```

6. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   # Create pull request on GitHub
   ```

### Code Style Guidelines

#### Python Code Style

We follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) with some modifications:

```python
# ✅ Good
def process_payment(amount: int, currency: str) -> PaymentResult:
    """Process a payment with the given amount and currency.
    
    Args:
        amount: Payment amount in cents
        currency: Three-letter currency code
        
    Returns:
        PaymentResult object with payment details
        
    Raises:
        PaymentError: If payment processing fails
    """
    if amount <= 0:
        raise ValueError("Amount must be positive")
    
    return PaymentResult(
        payment_id="pi_123",
        status="succeeded",
        amount=amount
    )

# ❌ Bad
def processPayment(amount,currency):
    if amount<=0:raise ValueError("Amount must be positive")
    return PaymentResult(payment_id="pi_123",status="succeeded",amount=amount)
```

#### Import Organization

```python
# Standard library imports
import os
import sys
from typing import Optional, List

# Third-party imports
import requests
import stripe

# Local imports
from aiagent_payments.core import PaymentProcessor
from aiagent_payments.exceptions import PaymentError
```

#### Type Hints

Always use type hints for function parameters and return values:

```python
from typing import Optional, List, Dict, Any

def create_customer(
    email: str,
    name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Customer:
    """Create a new customer."""
    pass
```

### Testing Guidelines

#### Test Structure

```python
import pytest
from aiagent_payments import PaymentProcessor

class TestPaymentProcessor:
    """Test cases for PaymentProcessor."""
    
    @pytest.fixture
    def processor(self):
        """Create a test processor instance."""
        return PaymentProcessor(provider="mock")
    
    def test_process_payment_success(self, processor):
        """Test successful payment processing."""
        result = processor.process_payment(
            amount=1000,
            currency="usd",
            description="Test payment"
        )
        
        assert result.status == "succeeded"
        assert result.amount == 1000
        assert result.currency == "usd"
    
    def test_process_payment_invalid_amount(self, processor):
        """Test payment with invalid amount."""
        with pytest.raises(ValueError, match="Amount must be positive"):
            processor.process_payment(
                amount=-100,
                currency="usd",
                description="Test payment"
            )
```

#### Test Coverage

- **Unit tests**: Test individual functions and classes
- **Integration tests**: Test interactions between components
- **Functional tests**: Test complete workflows
- **Edge cases**: Test error conditions and boundary values

### Documentation Guidelines

#### Docstrings

Use Google-style docstrings:

```python
def process_payment(
    amount: int,
    currency: str,
    description: str,
    metadata: Optional[Dict[str, Any]] = None
) -> PaymentResult:
    """Process a payment with the specified parameters.
    
    Args:
        amount: Payment amount in cents (e.g., 1000 for $10.00)
        currency: Three-letter currency code (e.g., "usd", "eur")
        description: Human-readable description of the payment
        metadata: Optional metadata to attach to the payment
        
    Returns:
        PaymentResult object containing payment details
        
    Raises:
        ValueError: If amount is negative or currency is invalid
        PaymentError: If payment processing fails
        
    Example:
        >>> processor = PaymentProcessor(provider="stripe")
        >>> result = processor.process_payment(1000, "usd", "Test payment")
        >>> print(result.status)
        'succeeded'
    """
    pass
```

#### README Updates

When adding new features, update relevant documentation:

- **Main README**: Add overview of new features
- **Examples**: Add working examples
- **API documentation**: Update docstrings
- **Wiki**: Update relevant wiki pages

## 🧪 Testing

### Running Tests

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run with coverage
python -m pytest --cov=aiagent_payments --cov-report=html

# Run specific test file
python -m pytest tests/unit/test_core.py

# Run specific test function
python -m pytest tests/unit/test_core.py::test_process_payment
```

### Writing Tests

#### Test Naming

```python
# ✅ Good test names
def test_process_payment_with_valid_amount():
    pass

def test_process_payment_raises_error_for_negative_amount():
    pass

def test_customer_creation_with_optional_fields():
    pass

# ❌ Bad test names
def test_payment():
    pass

def test_error():
    pass
```

#### Test Organization

```python
class TestPaymentProcessor:
    """Test PaymentProcessor functionality."""
    
    class TestProcessPayment:
        """Test payment processing methods."""
        
        def test_successful_payment(self):
            """Test successful payment processing."""
            pass
        
        def test_failed_payment(self):
            """Test failed payment processing."""
            pass
    
    class TestCustomerManagement:
        """Test customer management methods."""
        
        def test_create_customer(self):
            """Test customer creation."""
            pass
        
        def test_update_customer(self):
            """Test customer updates."""
            pass
```

## 📝 Pull Request Guidelines

### PR Checklist

Before submitting a PR, ensure:

- [ ] **Tests pass** - All tests should pass
- [ ] **Code is formatted** - Run `make format`
- [ ] **Linting passes** - Run `make lint`
- [ ] **Type checking passes** - Run `make type-check`
- [ ] **Documentation updated** - Update relevant docs
- [ ] **Examples work** - Test any new examples
- [ ] **Commit messages follow convention** - Use conventional commits

### PR Template

```markdown
## Description
Brief description of changes made.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] My code follows the style guidelines of this project
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
```

### Commit Message Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```bash
git commit -m "feat(stripe): add support for stablecoin payments"
git commit -m "fix(core): handle null values in payment processing"
git commit -m "docs(readme): update installation instructions"
git commit -m "test(providers): add comprehensive test coverage"
```

## 🔒 Security

### Security Guidelines

- **Never commit secrets** - API keys, passwords, etc.
- **Use environment variables** - For configuration
- **Validate inputs** - Always validate user inputs
- **Handle errors securely** - Don't expose sensitive information
- **Follow OWASP guidelines** - For web security

### Reporting Security Issues

For security issues, please:

1. **Don't open a public issue**
2. **Email security@yourdomain.com** (if available)
3. **Or contact maintainers directly**

## 🏷️ Release Process

### Versioning

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

- [ ] **Update version** in `pyproject.toml`
- [ ] **Update changelog** with new features/fixes
- [ ] **Run full test suite** - All tests must pass
- [ ] **Update documentation** - Ensure docs are current
- [ ] **Create release notes** - Summarize changes
- [ ] **Tag release** - Create git tag
- [ ] **Publish to PyPI** - Release to package index

## 🤝 Community Guidelines

### Code of Conduct

We are committed to providing a welcoming and inclusive environment:

- **Be respectful** - Treat everyone with respect
- **Be helpful** - Help others learn and grow
- **Be constructive** - Provide constructive feedback
- **Be inclusive** - Welcome diverse perspectives

### Getting Help

- **GitHub Issues**: For bugs and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Documentation**: Check the wiki and examples first
- **Community**: Ask in discussions for help

## 📚 Resources

### Development Resources

- **[Python Style Guide](https://www.python.org/dev/peps/pep-0008/)**
- **[Conventional Commits](https://www.conventionalcommits.org/)**
- **[Semantic Versioning](https://semver.org/)**
- **[GitHub Flow](https://guides.github.com/introduction/flow/)**

### Project Resources

- **[Main Documentation](https://github.com/cmaliwal/aiagent-payments)**
- **[Examples](https://github.com/cmaliwal/aiagent-payments/tree/main/examples)**
- **[Issues](https://github.com/cmaliwal/aiagent-payments/issues)**
- **[Discussions](https://github.com/cmaliwal/aiagent-payments/discussions)**

## 🙏 Recognition

Contributors will be recognized in:

- **README.md** - List of contributors
- **CHANGELOG.md** - Credit for contributions
- **Release notes** - Mention in releases
- **Documentation** - Credit in relevant docs

---

**Thank you for contributing to AIAgent Payments!** 🚀

Your contributions help make this project better for everyone in the community. 