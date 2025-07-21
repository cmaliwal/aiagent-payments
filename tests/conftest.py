"""
conftest.py: Shared pytest fixtures for the aiagent_payments test suite.

- Place fixtures here to make them available across all test subdirectories.
- Example: tmp_path, mock storage, test data, etc.

Usage:
    def test_something(payment_manager):
        assert payment_manager is not None
    def test_file_storage_manager(file_storage_manager, tmp_path):
        assert file_storage_manager is not None
"""

from unittest.mock import MagicMock, patch

import pytest

from aiagent_payments import PaymentManager
from aiagent_payments.storage import FileStorage, MemoryStorage


@pytest.fixture
def payment_manager():
    """A PaymentManager instance with in-memory storage for fast, isolated tests."""
    return PaymentManager(storage=MemoryStorage())


@pytest.fixture
def file_storage_manager(tmp_path):
    """A PaymentManager instance with file-based storage for integration tests."""
    return PaymentManager(storage=FileStorage(str(tmp_path)))


@pytest.fixture
def mock_web3():
    """Mock Web3 instance for testing."""
    mock_web3_instance = MagicMock()
    mock_web3_instance.eth.contract.return_value = MagicMock()
    mock_web3_instance.eth.get_transaction_receipt.return_value = {
        "status": 1,
        "blockNumber": 12345,
    }
    mock_web3_instance.eth.get_transaction.return_value = {
        "to": "0x1234567890123456789012345678901234567890",
        "value": 1000000000000000000,  # 1 ETH in wei
        "gas": 21000,
        "gasPrice": 20000000000,
    }
    return mock_web3_instance


@pytest.fixture
def mock_web3_provider(monkeypatch):
    """Mock Web3 HTTPProvider for testing."""
    mock_web3_instance = MagicMock()
    monkeypatch.setattr("web3.Web3.HTTPProvider", lambda *args, **kwargs: None)
    return mock_web3_instance
