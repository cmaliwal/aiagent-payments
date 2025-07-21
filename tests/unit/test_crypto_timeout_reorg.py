"""
Test timeout validation and reorg protection fixes for CryptoProvider.

This test suite validates the critical fixes for:
1. Transaction timeout validation and fallback handling
2. Enhanced reorg protection with safety margin
3. Malformed timeout handling
4. Production readiness checks

Author: AI Agent Payments Team
Version: 0.0.1b1
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

INFURA_PROJECT_ID = os.environ.get("INFURA_PROJECT_ID")

pytestmark = pytest.mark.skipif(not INFURA_PROJECT_ID, reason="INFURA_PROJECT_ID not set; skipping real Infura tests.")

# Mock web3 before importing CryptoProvider
with patch.dict("sys.modules", {"web3": Mock()}):
    from aiagent_payments.exceptions import ProviderError, ValidationError
    from aiagent_payments.models import PaymentTransaction
    from aiagent_payments.providers.crypto import CryptoProvider
    from aiagent_payments.storage.memory import MemoryStorage


class TestTimeoutValidation:
    """Test transaction timeout validation and fallback handling."""

    @pytest.fixture
    def crypto_provider(self):
        """Create a CryptoProvider instance for testing."""
        with patch("aiagent_payments.providers.crypto.Web3") as mock_web3:
            # Mock web3 connection
            mock_w3 = Mock()
            mock_w3.is_connected.return_value = True
            mock_w3.eth.chain_id = 11155111  # Sepolia
            mock_w3.eth.block_number = 1000000
            mock_w3.eth.gas_price = 20000000000  # 20 gwei
            mock_w3.to_checksum_address.return_value = "0x1234567890123456789012345678901234567890"
            mock_w3.is_address.return_value = True
            mock_w3.from_wei.return_value = 20.0

            # Mock contract
            mock_contract = Mock()
            mock_contract.functions.decimals.return_value.call.return_value = 6
            mock_contract.functions.symbol.return_value.call.return_value = "USDT"
            mock_contract.functions.name.return_value.call.return_value = "Tether USD"
            mock_contract.address = "0x7169D38820dfd117C3FA1f22a697dBA58d90BA06"

            mock_web3.return_value = mock_w3
            mock_web3.HTTPProvider.return_value = Mock()

            # Set dev mode
            os.environ["AIAgentPayments_DevMode"] = "1"

            provider = CryptoProvider(
                wallet_address="0x1234567890123456789012345678901234567890", network="sepolia", storage=MemoryStorage()
            )
            provider.w3 = mock_w3
            provider.usdt_contract = mock_contract
            provider.usdt_decimals = 6
            provider.usdt_symbol = "USDT"
            provider.usdt_name = "Tether USD"

            return provider

    def test_timeout_validation_in_process_payment(self, crypto_provider):
        """Test that timeout validation works correctly in process_payment."""
        # Test successful timeout validation
        transaction = crypto_provider.process_payment(user_id="test_user", amount=10.0, currency="USD")

        # Verify timeout is set and validated
        assert "timeout_at" in transaction.metadata
        assert transaction.metadata["timeout_minutes"] == 30
        assert transaction.metadata["timeout_validated"] is True

        # Verify timeout is future-dated
        timeout_at = datetime.fromisoformat(transaction.metadata["timeout_at"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        assert timeout_at > now
        assert (timeout_at - now).total_seconds() > 1700  # At least 28 minutes

    def test_timeout_fallback_in_verify_payment_missing_timeout(self, crypto_provider):
        """Test fallback timeout when timeout_at is missing."""
        # Create transaction without timeout_at
        transaction = PaymentTransaction(
            id="test_tx_1",
            user_id="test_user",
            amount=10.0,
            currency="USD",
            payment_method="crypto_usdt",
            status="pending",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=35),  # 35 minutes ago
            completed_at=None,
            metadata={
                "crypto_type": "usdt",
                "network": "sepolia",
                "wallet_address": crypto_provider.wallet_address,
                "usdt_amount_wei": 10000000,  # 10 USDT
            },
        )

        # Save transaction
        crypto_provider.storage.save_transaction(transaction)

        # Verify payment should fail due to timeout
        result = crypto_provider.verify_payment("test_tx_1")
        assert result is False

        # Check transaction status
        updated_transaction = crypto_provider.storage.get_transaction("test_tx_1")
        assert updated_transaction.status == "failed"
        assert "timed out" in updated_transaction.metadata["failure_reason"]

    def test_timeout_fallback_in_verify_payment_invalid_format(self, crypto_provider):
        """Test fallback timeout when timeout_at has invalid format."""
        # Create transaction with invalid timeout_at
        transaction = PaymentTransaction(
            id="test_tx_2",
            user_id="test_user",
            amount=10.0,
            currency="USD",
            payment_method="crypto_usdt",
            status="pending",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=35),  # 35 minutes ago
            completed_at=None,
            metadata={
                "crypto_type": "usdt",
                "network": "sepolia",
                "wallet_address": crypto_provider.wallet_address,
                "usdt_amount_wei": 10000000,  # 10 USDT
                "timeout_at": "invalid-iso-format",  # Invalid format
            },
        )

        # Save transaction
        crypto_provider.storage.save_transaction(transaction)

        # Verify payment should fail due to timeout
        result = crypto_provider.verify_payment("test_tx_2")
        assert result is False

        # Check transaction status
        updated_transaction = crypto_provider.storage.get_transaction("test_tx_2")
        assert updated_transaction.status == "failed"
        assert "invalid timeout format" in updated_transaction.metadata["failure_reason"]

    def test_timeout_validation_info(self, crypto_provider):
        """Test timeout validation info method."""
        info = crypto_provider.get_timeout_validation_info()

        assert info["timeout_minutes"] == 30
        assert info["timeout_validation_enabled"] is True
        assert info["fallback_timeout_enabled"] is True
        assert info["fallback_timeout_minutes"] == 30
        assert info["timeout_format"] == "ISO 8601"
        assert "Future-dated timeout validation" in info["validation_features"]
        assert "Fallback to created_at + 30 minutes" in info["validation_features"]


class TestReorgProtection:
    """Test enhanced reorg protection with safety margin."""

    @pytest.fixture
    def crypto_provider(self):
        """Create a CryptoProvider instance for testing."""
        with patch("aiagent_payments.providers.crypto.Web3") as mock_web3:
            # Mock web3 connection
            mock_w3 = Mock()
            mock_w3.is_connected.return_value = True
            mock_w3.eth.chain_id = 11155111  # Sepolia
            mock_w3.eth.block_number = 1000000
            mock_w3.eth.gas_price = 20000000000  # 20 gwei
            mock_w3.to_checksum_address.return_value = "0x1234567890123456789012345678901234567890"
            mock_w3.is_address.return_value = True
            mock_w3.from_wei.return_value = 20.0

            # Mock contract
            mock_contract = Mock()
            mock_contract.functions.decimals.return_value.call.return_value = 6
            mock_contract.functions.symbol.return_value.call.return_value = "USDT"
            mock_contract.functions.name.return_value.call.return_value = "Tether USD"
            mock_contract.address = "0x7169D38820dfd117C3FA1f22a697dBA58d90BA06"

            mock_web3.return_value = mock_w3
            mock_web3.HTTPProvider.return_value = Mock()

            # Set dev mode
            os.environ["AIAgentPayments_DevMode"] = "1"

            provider = CryptoProvider(
                wallet_address="0x1234567890123456789012345678901234567890",
                network="sepolia",
                confirmations_required=6,  # Testnet default
                storage=MemoryStorage(),
            )
            provider.w3 = mock_w3
            provider.usdt_contract = mock_contract
            provider.usdt_decimals = 6
            provider.usdt_symbol = "USDT"
            provider.usdt_name = "Tether USD"

            return provider

    def test_reorg_protection_info(self, crypto_provider):
        """Test reorg protection info method."""
        info = crypto_provider.get_reorg_protection_info()

        assert info["confirmations_required"] == 6
        assert info["safety_margin_confirmations"] == 5
        assert info["effective_confirmations"] == 11  # 6 + 5
        assert info["reorg_protection_enabled"] is True
        assert info["canonical_chain_verification"] is True
        assert info["safety_margin_enabled"] is True
        assert info["reorg_risk_assessment"] == "MODERATE"  # 11 confirmations

    def test_reorg_protection_mainnet(self):
        """Test reorg protection for mainnet configuration."""
        with patch("aiagent_payments.providers.crypto.Web3") as mock_web3:
            # Mock web3 connection
            mock_w3 = Mock()
            mock_w3.is_connected.return_value = True
            mock_w3.eth.chain_id = 1  # Mainnet
            mock_w3.eth.block_number = 10000000
            mock_w3.eth.gas_price = 20000000000  # 20 gwei
            mock_w3.to_checksum_address.return_value = "0x1234567890123456789012345678901234567890"
            mock_w3.is_address.return_value = True
            mock_w3.from_wei.return_value = 20.0

            # Mock contract
            mock_contract = Mock()
            mock_contract.functions.decimals.return_value.call.return_value = 6
            mock_contract.functions.symbol.return_value.call.return_value = "USDT"
            mock_contract.functions.name.return_value.call.return_value = "Tether USD"
            mock_contract.address = "0xdAC17F958D2ee523a2206206994597C13D831ec7"

            mock_web3.return_value = mock_w3
            mock_web3.HTTPProvider.return_value = Mock()

            # Set dev mode
            os.environ["AIAgentPayments_DevMode"] = "1"

            provider = CryptoProvider(
                wallet_address="0x1234567890123456789012345678901234567890",
                network="mainnet",
                confirmations_required=24,  # Mainnet default
                storage=MemoryStorage(),
            )
            provider.w3 = mock_w3
            provider.usdt_contract = mock_contract
            provider.usdt_decimals = 6
            provider.usdt_symbol = "USDT"
            provider.usdt_name = "Tether USD"

            info = provider.get_reorg_protection_info()

            assert info["confirmations_required"] == 24
            assert info["safety_margin_confirmations"] == 5
            assert info["effective_confirmations"] == 29  # 24 + 5
            assert info["reorg_risk_assessment"] == "LOW"  # 29 confirmations

    def test_verify_transfer_event_with_safety_margin(self, crypto_provider):
        """Test that verify_transfer_event_with_confirmations uses safety margin."""
        # Mock the verification method to check safety margin usage
        with patch.object(crypto_provider, "_verify_transfer_event_with_confirmations") as mock_verify:
            mock_verify.return_value = False

            # Create a transaction
            transaction = PaymentTransaction(
                id="test_tx_3",
                user_id="test_user",
                amount=10.0,
                currency="USD",
                payment_method="crypto_usdt",
                status="pending",
                created_at=datetime.now(timezone.utc),
                completed_at=None,
                metadata={
                    "crypto_type": "usdt",
                    "network": "sepolia",
                    "wallet_address": crypto_provider.wallet_address,
                    "usdt_amount_wei": 10000000,  # 10 USDT
                    "timeout_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
                },
            )

            crypto_provider.storage.save_transaction(transaction)

            # Call verify_payment
            crypto_provider.verify_payment("test_tx_3")

            # Verify the method was called
            mock_verify.assert_called_once_with("test_tx_3", 10000000)


class TestProductionReadiness:
    """Test production readiness checks with new features."""

    @pytest.fixture
    def crypto_provider(self):
        """Create a CryptoProvider instance for testing."""
        with patch("aiagent_payments.providers.crypto.Web3") as mock_web3:
            # Mock web3 connection
            mock_w3 = Mock()
            mock_w3.is_connected.return_value = True
            mock_w3.eth.chain_id = 11155111  # Sepolia
            mock_w3.eth.block_number = 1000000
            mock_w3.eth.gas_price = 20000000000  # 20 gwei
            mock_w3.to_checksum_address.return_value = "0x1234567890123456789012345678901234567890"
            mock_w3.is_address.return_value = True
            mock_w3.from_wei.return_value = 20.0

            # Mock contract
            mock_contract = Mock()
            mock_contract.functions.decimals.return_value.call.return_value = 6
            mock_contract.functions.symbol.return_value.call.return_value = "USDT"
            mock_contract.functions.name.return_value.call.return_value = "Tether USD"
            mock_contract.address = "0x7169D38820dfd117C3FA1f22a697dBA58d90BA06"

            mock_web3.return_value = mock_w3
            mock_web3.HTTPProvider.return_value = Mock()

            # Set dev mode
            os.environ["AIAgentPayments_DevMode"] = "1"

            provider = CryptoProvider(
                wallet_address="0x1234567890123456789012345678901234567890", network="sepolia", storage=MemoryStorage()
            )
            provider.w3 = mock_w3
            provider.usdt_contract = mock_contract
            provider.usdt_decimals = 6
            provider.usdt_symbol = "USDT"
            provider.usdt_name = "Tether USD"

            return provider

    def test_health_check_includes_new_features(self, crypto_provider):
        """Test that health check includes timeout and reorg protection checks."""
        # Mock the health check methods
        with patch.object(crypto_provider, "get_timeout_validation_info") as mock_timeout:
            with patch.object(crypto_provider, "get_reorg_protection_info") as mock_reorg:
                mock_timeout.return_value = {"timeout_validation_enabled": True}
                mock_reorg.return_value = {"effective_confirmations": 11}

                # Health check should not raise an exception
                result = crypto_provider.health_check()
                assert result is True

                # Verify methods were called
                mock_timeout.assert_called_once()
                mock_reorg.assert_called_once()

    def test_production_readiness_checks(self, crypto_provider):
        """Test production readiness includes new validation features."""
        readiness = crypto_provider.is_production_ready()

        # Should not be production ready in dev mode
        assert readiness["is_production_ready"] is False
        assert readiness["dev_mode"] is True

        # Check that timeout and reorg features are documented
        timeout_info = crypto_provider.get_timeout_validation_info()
        reorg_info = crypto_provider.get_reorg_protection_info()

        assert timeout_info["timeout_validation_enabled"] is True
        assert reorg_info["reorg_protection_enabled"] is True


class TestIntegrationScenarios:
    """Test integration scenarios for the fixes."""

    @pytest.fixture
    def crypto_provider(self):
        """Create a CryptoProvider instance for testing."""
        with patch("aiagent_payments.providers.crypto.Web3") as mock_web3:
            # Mock web3 connection
            mock_w3 = Mock()
            mock_w3.is_connected.return_value = True
            mock_w3.eth.chain_id = 11155111  # Sepolia
            mock_w3.eth.block_number = 1000000
            mock_w3.eth.gas_price = 20000000000  # 20 gwei
            mock_w3.to_checksum_address.return_value = "0x1234567890123456789012345678901234567890"
            mock_w3.is_address.return_value = True
            mock_w3.from_wei.return_value = 20.0

            # Mock contract
            mock_contract = Mock()
            mock_contract.functions.decimals.return_value.call.return_value = 6
            mock_contract.functions.symbol.return_value.call.return_value = "USDT"
            mock_contract.functions.name.return_value.call.return_value = "Tether USD"
            mock_contract.address = "0x7169D38820dfd117C3FA1f22a697dBA58d90BA06"

            mock_web3.return_value = mock_w3
            mock_web3.HTTPProvider.return_value = Mock()

            # Set dev mode
            os.environ["AIAgentPayments_DevMode"] = "1"

            provider = CryptoProvider(
                wallet_address="0x1234567890123456789012345678901234567890", network="sepolia", storage=MemoryStorage()
            )
            provider.w3 = mock_w3
            provider.usdt_contract = mock_contract
            provider.usdt_decimals = 6
            provider.usdt_symbol = "USDT"
            provider.usdt_name = "Tether USD"

            return provider

    def test_concurrent_transaction_processing(self, crypto_provider):
        """Test concurrent transaction processing with timeout validation."""
        import threading
        import time

        results = []
        errors = []

        def process_transaction(user_id):
            try:
                transaction = crypto_provider.process_payment(user_id=user_id, amount=10.0, currency="USD")
                results.append(transaction.id)
            except Exception as e:
                errors.append(str(e))

        # Create 10 concurrent transactions
        threads = []
        for i in range(10):
            thread = threading.Thread(target=process_transaction, args=(f"user_{i}",))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all transactions were created successfully
        assert len(results) == 10
        assert len(errors) == 0

        # Verify all transactions have valid timeouts
        for tx_id in results:
            transaction = crypto_provider.storage.get_transaction(tx_id)
            assert "timeout_at" in transaction.metadata
            assert transaction.metadata["timeout_validated"] is True

    def test_malformed_timeout_recovery(self, crypto_provider):
        """Test recovery from malformed timeout values."""
        # Create transaction with malformed timeout
        transaction = PaymentTransaction(
            id="malformed_tx",
            user_id="test_user",
            amount=10.0,
            currency="USD",
            payment_method="crypto_usdt",
            status="pending",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=35),
            completed_at=None,
            metadata={
                "crypto_type": "usdt",
                "network": "sepolia",
                "wallet_address": crypto_provider.wallet_address,
                "usdt_amount_wei": 10000000,
                "timeout_at": "not-a-valid-iso-string",
            },
        )

        crypto_provider.storage.save_transaction(transaction)

        # Verify payment should handle malformed timeout gracefully
        result = crypto_provider.verify_payment("malformed_tx")
        assert result is False

        # Check that transaction was marked as failed with appropriate reason
        updated_transaction = crypto_provider.storage.get_transaction("malformed_tx")
        assert updated_transaction.status == "failed"
        assert "invalid timeout format" in updated_transaction.metadata["failure_reason"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
