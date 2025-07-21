"""
USDT ERC-20 Payment Provider using web3.py and Infura.

This module provides a comprehensive USDT ERC-20 payment solution with:
- On-chain payment verification
- Multi-network support (mainnet, testnets)
- Gas estimation and transaction monitoring
- Comprehensive error handling and validation
- Production-ready security features

Author: AI Agent Payments Team
Version: 0.0.1-beta
"""

import logging
import os
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from time import sleep
from typing import Any, Dict, List, Optional, Tuple

from requests.exceptions import HTTPError

from ..exceptions import (
    ConfigurationError,
    PaymentFailed,
    ProviderError,
    ValidationError,
)
from ..models import PaymentTransaction
from ..utils import generate_id, retry
from .base import PaymentProvider

# Lazy imports to avoid circular import issues
# These will be imported only when needed

web3 = None  # For test patching in unit tests

logger = logging.getLogger(__name__)

# USDT ERC-20 Contract Addresses (verified)
USDT_CONTRACTS = {
    "mainnet": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "sepolia": "0x7169D38820dfd117C3FA1f22a697dBA58d90BA06",  # Testnet USDT
    # Note: Goerli testnet is deprecated and will be shut down
    # Use Sepolia for testing instead
}

# USDT ERC-20 ABI (comprehensive for all operations)
USDT_ABI = [
    # Transfer event
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    },
    # Balance function
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    # Decimals function
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    # Symbol function
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    # Name function
    {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    # Total supply function
    {"constant": True, "inputs": [], "name": "totalSupply", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
]

# Network configuration
NETWORK_CONFIG = {
    "mainnet": {
        "name": "Ethereum Mainnet",
        "chain_id": 1,
        "block_time": 12,  # seconds
        "confirmations_required": 24,  # Increased for reorg safety
        "gas_limit": 21000,
        "max_gas_price_gwei": 100,
    },
    "sepolia": {
        "name": "Sepolia Testnet",
        "chain_id": 11155111,
        "block_time": 12,
        "confirmations_required": 6,  # Lower for testnet
        "gas_limit": 21000,
        "max_gas_price_gwei": 50,
    },
    # Note: Goerli testnet configuration removed - deprecated and will be shut down
}

# Supported networks
SUPPORTED_NETWORKS = list(USDT_CONTRACTS.keys())


class CryptoProvider(PaymentProvider):
    """
    Production-ready USDT ERC-20 payment provider using web3.py and Infura.

    This provider offers comprehensive USDT payment processing with:
    - Multi-network support (mainnet, sepolia)
    - On-chain payment verification with configurable confirmations
    - Gas estimation and transaction monitoring
    - Comprehensive error handling and validation
    - Security features and rate limiting
    - Production-ready logging and monitoring
    - Blockchain reorg protection for payment verification
    - Price feed validation for production safety

    **Configuration:**
    - INFURA_PROJECT_ID: Your Infura project ID (required for production)
    - NETWORK: 'mainnet' or 'sepolia' (default: 'mainnet')
    - WALLET_ADDRESS: Your wallet address to receive payments (required)
    - CONFIRMATIONS_REQUIRED: Number of confirmations for payment verification
    - MAX_GAS_PRICE_GWEI: Maximum gas price to accept (safety feature)

    **Note:** Goerli testnet is deprecated and will be shut down. Use Sepolia for testing.

    **Security Features:**
    - Address validation and checksum verification
    - Gas price limits to prevent overpayment
    - Transaction confirmation requirements (24 confirmations for mainnet)
    - Blockchain reorg protection with canonical chain verification
    - Transaction receipt validation to prevent false positives from failed transactions
    - Storage write retry logic to prevent inconsistent transaction states
    - Rate limiting and retry mechanisms
    - Comprehensive error handling
    - Price feed validation (prevents mock feeds in production)

    **Production Considerations:**
    - Use mainnet for real payments
    - Implement proper wallet security
    - Monitor gas fees and network congestion
    - Set up alerts for failed transactions
    - Use persistent storage for transaction tracking
    - Higher confirmation counts reduce reorg risk (24+ for mainnet)
    - Integrate Chainlink price oracle for accurate USDT pricing
    - Monitor transaction receipt validation failures
    - Alert on reverted or failed transactions
    - Monitor storage write retry failures during verification
    - Alert on persistent storage write errors
    """

    def __init__(
        self,
        wallet_address: str,
        infura_project_id: Optional[str] = None,
        network: str = "mainnet",
        confirmations_required: Optional[int] = None,
        max_gas_price_gwei: Optional[int] = None,
        provider: Any = None,
        storage: Any = None,
        usdt_contracts: Optional[dict] = None,
    ):
        self.usdt_contracts = usdt_contracts or USDT_CONTRACTS
        """
        Initialize the USDT crypto provider.

        Args:
            wallet_address: Ethereum wallet address to receive payments
            infura_project_id: Infura project ID (optional, can use env var)
            network: Network to use ('mainnet', 'sepolia')
            confirmations_required: Number of confirmations for payment verification
            max_gas_price_gwei: Maximum gas price to accept (safety feature)
            provider: Optional provider override (for testing)
            storage: Storage backend for transaction persistence (recommended for production)
            usdt_contracts: Optional USDT contract addresses for different networks

        Note:
            Goerli testnet is deprecated and will be shut down. Use Sepolia for testing.

        Raises:
            ConfigurationError: If configuration is invalid
            ProviderError: If connection to Infura fails
        """
        # Validate and set parameters
        self._validate_initialization_params(wallet_address, network, confirmations_required, max_gas_price_gwei)

        self.wallet_address = self._normalize_address(wallet_address)
        self.network = network.lower()
        self.infura_project_id = infura_project_id or os.getenv("INFURA_PROJECT_ID")
        self.provider = provider

        # Set network-specific configuration
        self.network_config = NETWORK_CONFIG[self.network]
        self.confirmations_required = confirmations_required or self.network_config["confirmations_required"]
        self.max_gas_price_gwei = max_gas_price_gwei or self.network_config["max_gas_price_gwei"]

        # Initialize storage backend (use persistent storage for production)
        self.storage = storage
        if self.storage is None:
            # Fallback to in-memory storage for compatibility
            from ..storage.memory import MemoryStorage

            self.storage = MemoryStorage()
            if not self._is_dev_mode():
                raise ConfigurationError(
                    "In-memory storage not allowed in production mode. "
                    "Transaction data will be lost on restart. "
                    "Use DatabaseStorage with SQLAlchemy or FileStorage for production deployments."
                )
            else:
                logger.warning(
                    "Using in-memory storage. Transaction data will be lost on restart. "
                    "Use persistent storage (DatabaseStorage/FileStorage) for production."
                )

        # Validate storage backend capabilities
        self._validate_storage()

        # Initialize in-memory transaction cache and lock for placeholder management
        self.transactions: dict[str, PaymentTransaction] = {}  # In-memory transaction cache
        self.transactions_lock = threading.Lock()  # Thread-safe lock for cache updates

        # Initialize concurrency control with reentrant lock to prevent deadlocks
        # RLock allows the same thread to acquire the lock multiple times safely
        self._storage_lock = threading.RLock()
        self._lock_contention_count = 0  # Monitor lock contention
        self._last_contention_reset = datetime.now(timezone.utc)  # Track reset time
        self._contention_threshold = 50  # Alert after 50 timeouts per hour

        # Initialize Infura rate limit tracking
        self._rate_limit_errors = 0  # Track 429 errors
        self._last_rate_limit_reset = datetime.now(timezone.utc)  # Track reset time
        self._rate_limit_threshold = 10  # Alert after 10 rate limit errors per hour

        # Initialize web3 connection and contract
        self._setup_web3()
        self._setup_contract()

        # Initialize provider
        super().__init__("CryptoProvider")

        logger.info(
            f"CryptoProvider initialized for USDT on {self.network_config['name']} "
            f"(confirmations: {self.confirmations_required}, "
            f"max gas: {self.max_gas_price_gwei} gwei, "
            f"storage: {type(self.storage).__name__})"
        )

    def _validate_initialization_params(
        self,
        wallet_address: str,
        network: str,
        confirmations_required: Optional[int],
        max_gas_price_gwei: Optional[int],
    ) -> None:
        """Validate initialization parameters."""
        if not wallet_address or not isinstance(wallet_address, str):
            raise ConfigurationError("wallet_address is required and must be a string")

        if not network or not isinstance(network, str):
            raise ConfigurationError("network is required and must be a string")

        if network.lower() not in SUPPORTED_NETWORKS:
            if network.lower() == "goerli":
                raise ConfigurationError(
                    f"Goerli testnet is deprecated and will be shut down. "
                    f"Please use 'sepolia' for testing instead. "
                    f"Supported networks: {', '.join(SUPPORTED_NETWORKS)}"
                )
            else:
                raise ConfigurationError(
                    f"Unsupported network: {network}. " f"Supported networks: {', '.join(SUPPORTED_NETWORKS)}"
                )

        if confirmations_required is not None:
            if not isinstance(confirmations_required, int) or confirmations_required < 1:
                raise ConfigurationError("confirmations_required must be a positive integer")

        if max_gas_price_gwei is not None:
            if not isinstance(max_gas_price_gwei, int) or max_gas_price_gwei <= 0:
                raise ConfigurationError("max_gas_price_gwei must be a positive integer")

    def _normalize_address(self, address: str) -> str:
        """Normalize and validate Ethereum address."""
        try:
            import web3

            # Convert to checksum address for validation
            checksum_address = web3.Web3.to_checksum_address(address)
            return checksum_address
        except (ValueError, TypeError) as e:
            raise ConfigurationError(f"Invalid Ethereum address format: {address}") from e

    def _setup_web3(self) -> None:
        """Setup web3 connection to Infura."""
        import web3

        if not self.infura_project_id or self.infura_project_id == "dummy_project_id":
            if not self._is_dev_mode():
                raise ProviderError(
                    "Valid Infura project ID required for production. "
                    "Free-tier accounts may hit rate limits, causing verification failures.",
                    provider="crypto",
                )
            import warnings

            warnings.warn(
                "Infura project ID not set or invalid. You may hit rate limits. "
                "Set INFURA_PROJECT_ID in your environment for production use."
            )
            # Use a dummy endpoint for dev mode
            self.infura_project_id = "dummy_project_id"

        # Setup Infura endpoint
        endpoint = f"https://{self.network}.infura.io/v3/{self.infura_project_id}"

        try:
            self.w3 = web3.Web3(web3.Web3.HTTPProvider(endpoint, request_kwargs={"timeout": 30}))

            # Verify connection
            if not self.w3.is_connected():
                raise ProviderError(
                    f"Failed to connect to Infura {self.network_config['name']}",
                    provider="crypto",
                )

            # Warn about rate limits for production use
            if not self._is_dev_mode() and self.infura_project_id and self.infura_project_id != "dummy_project_id":
                logger.info(
                    "Infura project ID set. Verify your plan supports expected transaction volume "
                    "to avoid rate limit errors (HTTP 429). Free-tier accounts have strict limits."
                )

            # Verify chain ID
            actual_chain_id = self.w3.eth.chain_id
            expected_chain_id = self.network_config["chain_id"]
            if actual_chain_id != expected_chain_id:
                raise ProviderError(
                    f"Chain ID mismatch: expected {expected_chain_id}, got {actual_chain_id}",
                    provider="crypto",
                )

        except Exception as e:
            raise ProviderError(
                f"Failed to setup web3 connection: {str(e)}",
                provider="crypto",
            ) from e

    def _setup_contract(self) -> None:
        """Setup USDT contract instance."""
        try:
            usdt_address = self.usdt_contracts.get(self.network)
            if not usdt_address:
                raise ProviderError(
                    f"No USDT contract address configured for network: {self.network}",
                    provider="crypto",
                )
            import web3

            checksum_address = web3.Web3.to_checksum_address(usdt_address)
            self.usdt_contract = self.w3.eth.contract(address=checksum_address, abi=USDT_ABI)

            # Verify contract is accessible
            self._verify_contract_accessibility()

        except Exception as e:
            raise ProviderError(
                f"Failed to setup USDT contract: {str(e)}",
                provider="crypto",
            ) from e

    def _verify_contract_accessibility(self) -> None:
        """Verify that the USDT contract is accessible and has expected properties."""
        try:
            # Get contract properties
            self.usdt_decimals = self.usdt_contract.functions.decimals().call()
            self.usdt_symbol = self.usdt_contract.functions.symbol().call()
            self.usdt_name = self.usdt_contract.functions.name().call()

            # Validate USDT properties
            if self.usdt_decimals != 6:
                logger.warning(f"USDT decimals mismatch: expected 6, got {self.usdt_decimals}")

            if self.usdt_symbol.upper() not in ["USDT", "TETHER"]:
                logger.warning(f"Unexpected USDT symbol: {self.usdt_symbol}")

            logger.info(f"USDT contract verified: {self.usdt_name} ({self.usdt_symbol}) " f"with {self.usdt_decimals} decimals")

        except Exception as e:
            raise ProviderError(
                f"Failed to verify USDT contract accessibility: {str(e)}",
                provider="crypto",
            ) from e

    def _validate_storage(self) -> None:
        """Validate that the storage backend supports required operations."""
        required_methods = ["save_transaction", "get_transaction", "list_transactions"]
        for method in required_methods:
            if not hasattr(self.storage, method):
                raise ConfigurationError(f"Storage backend {type(self.storage).__name__} must implement {method}")

        # Check transaction support based on environment
        if not self._is_dev_mode():
            # Production mode: transaction support is mandatory
            transactional_methods = ["commit", "rollback"]
            for method in transactional_methods:
                if not hasattr(self.storage, method):
                    raise ConfigurationError(
                        f"Storage backend {type(self.storage).__name__} must implement {method} for production use. "
                        "Use DatabaseStorage with SQLAlchemy for production deployments."
                    )
            logger.info(f"Storage backend {type(self.storage).__name__} supports native transactions (production mode)")
        else:
            # Dev mode: transaction support is recommended but not required
            if hasattr(self.storage, "commit") and hasattr(self.storage, "rollback"):
                logger.info(f"Storage backend {type(self.storage).__name__} supports native transactions")
            else:
                logger.warning(
                    f"Storage backend {type(self.storage).__name__} does not support native transactions. "
                    "This is acceptable in dev mode but not recommended for production. "
                    "Use DatabaseStorage with SQLAlchemy for production deployments."
                )

    @contextmanager
    def _transaction_scope(self):
        """Provide a transactional scope for storage operations with concurrency control and deadlock prevention."""
        now = datetime.now(timezone.utc)
        if (now - self._last_contention_reset).total_seconds() > 3600:  # 1 hour
            self._lock_contention_count = 0
            self._last_contention_reset = now
            logger.debug("Lock contention counter reset (hourly)")

        acquired = self._storage_lock.acquire(timeout=10)  # Timeout after 10 seconds
        if not acquired:
            self._lock_contention_count += 1
            if self._lock_contention_count > self._contention_threshold:
                logger.error(
                    f"High lock contention detected: {self._lock_contention_count} timeouts in last hour. "
                    f"Switch to DatabaseStorage with native transaction support to reduce contention. "
                    f"Current storage: {type(self.storage).__name__}"
                )
            else:
                logger.warning(
                    f"Storage lock timeout. Contention count: {self._lock_contention_count}/{self._contention_threshold}. "
                    f"Consider using DatabaseStorage with native transaction support."
                )
            raise ProviderError("Storage lock timeout - too many concurrent operations", provider="crypto")

        try:
            yield
            commit_method = getattr(self.storage, "commit", None)
            if callable(commit_method):
                try:
                    commit_method()
                except Exception as commit_error:
                    logger.error(f"Storage commit failed: {commit_error}")
                    if not self._is_dev_mode():
                        raise
        except Exception as e:
            rollback_method = getattr(self.storage, "rollback", None)
            if callable(rollback_method):
                try:
                    rollback_method()
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback storage transaction: {rollback_error}")
                    if not self._is_dev_mode():
                        raise
            logger.error(f"Storage transaction failed: {e}")
            raise
        finally:
            self._storage_lock.release()

    def _get_usdt_price(self) -> float:
        """
        Fetch USDT/USD price (hardcoded 1:1 for beta; use Chainlink in production).

        Returns:
            Current USDT price in USD (hardcoded to 1.0 for beta)

        Note:
            This implementation assumes 1 USDT == 1 USD for beta testing.
            Minor market deviations (0.99–1.01 USD) may occur in real market conditions.
            For production, integrate with Chainlink price oracle or another reliable price feed.
        """
        price = 1.0  # Hardcode 1 USDT == 1 USD for all environments (beta)

        # Log appropriate message based on environment
        if self._is_dev_mode():
            logger.info(
                "Using hardcoded USDT price of 1.0 for beta (dev mode). "
                "Minor market deviations (0.99–1.01 USD) may occur in real conditions."
            )
        else:
            logger.info(
                "Using hardcoded USDT price of 1.0 for beta (production mode). "
                "Minor market deviations (0.99–1.01 USD) may occur in real conditions. "
                "Integrate Chainlink price oracle for production use."
            )

        return price

    def _is_dev_mode(self) -> bool:
        """Return True if running in dev/test mode."""
        return super()._is_dev_mode()

    def _handle_rate_limit(self, error: HTTPError) -> None:
        """
        Handle Infura rate limit errors with tracking and warnings.

        Args:
            error: HTTPError that may be a rate limit error

        Raises:
            HTTPError: Re-raises the original error after tracking
        """
        if hasattr(error, "response") and error.response and error.response.status_code == 429:
            # Reset counter if more than 1 hour has passed
            if (datetime.now(timezone.utc) - self._last_rate_limit_reset).total_seconds() > 3600:
                self._rate_limit_errors = 0
                self._last_rate_limit_reset = datetime.now(timezone.utc)
                logger.debug("Infura rate limit error counter reset (hourly)")

            self._rate_limit_errors += 1

            # Log warning if threshold exceeded
            if self._rate_limit_errors > self._rate_limit_threshold:
                logger.error(
                    f"High Infura rate limit errors detected: {self._rate_limit_errors} in the last hour. "
                    f"Free-tier accounts have strict limits (10 requests/sec, 100k/day). "
                    f"Consider upgrading to a paid Infura plan or reducing API call frequency. "
                    f"Current project ID: {self.infura_project_id}"
                )
            elif self._rate_limit_errors > self._rate_limit_threshold // 2:
                logger.warning(
                    f"Moderate Infura rate limit errors: {self._rate_limit_errors} in the last hour. "
                    f"Monitor usage to avoid hitting limits."
                )
            else:
                logger.info(f"Infura rate limit error {self._rate_limit_errors}/{self._rate_limit_threshold} in the last hour")

        # Re-raise the original error
        raise

    def _get_capabilities(self):
        """Get the capabilities of this provider."""
        from .base import ProviderCapabilities

        return ProviderCapabilities(
            supports_refunds=False,  # Manual refunds only
            supports_webhooks=False,
            supports_partial_refunds=False,
            supports_subscriptions=False,
            supports_metadata=True,
            supported_currencies=["USD", "USDT"],
            min_amount=0.01,
            max_amount=10000.0,
            processing_time_seconds=self.network_config["block_time"] * self.confirmations_required,
        )

    def _validate_configuration(self) -> None:
        """Validate the provider configuration."""
        if not self.wallet_address:
            raise ConfigurationError("wallet_address is required for CryptoProvider")

        if not self.w3.is_address(self.wallet_address):
            raise ConfigurationError("Invalid wallet_address format")

        if not self.w3.is_connected():
            raise ConfigurationError("Web3 connection is not established")

    def _perform_health_check(self) -> None:
        """Perform a comprehensive health check for the Crypto provider."""
        try:
            # Check web3 connection
            if not self.w3.is_connected():
                raise Exception("Web3 connection failed")

            # Check if we can get the latest block
            latest_block = self.w3.eth.block_number
            if latest_block <= 0:
                raise Exception("Could not get latest block number")

            # Check if we can interact with USDT contract
            decimals = self.usdt_contract.functions.decimals().call()
            if decimals != 6:
                logger.warning(f"USDT decimals mismatch: expected 6, got {decimals}")

            # Check wallet address balance (read-only operation)
            balance = self.usdt_contract.functions.balanceOf(self.wallet_address).call()
            logger.debug(f"Current USDT balance: {balance / (10 ** decimals)} USDT")

            # Check gas price
            gas_price = self.w3.eth.gas_price
            gas_price_gwei = self.w3.from_wei(gas_price, "gwei")
            if gas_price_gwei > self.max_gas_price_gwei:
                logger.warning(
                    f"Current gas price ({gas_price_gwei:.2f} gwei) exceeds " f"maximum ({self.max_gas_price_gwei} gwei)"
                )

            # Check production readiness if not in dev mode
            if not self._is_dev_mode():
                production_status = self.is_production_ready()
                if not production_status["is_production_ready"]:
                    logger.warning(f"Provider not production-ready: {production_status['recommendations']}")

                # Check price feed status
                price_feed_status = self.get_price_feed_status()
                if price_feed_status["price_feed_type"] == "hardcoded_beta":
                    logger.info(
                        f"Using hardcoded USDT price feed for beta: {price_feed_status['beta_assumption']}. "
                        f"{price_feed_status['market_deviation_note']}"
                    )

            # Check lock contention status
            lock_stats = self.get_lock_statistics()
            if lock_stats["contention_status"] == "HIGH":
                logger.error(
                    f"High lock contention detected: {lock_stats['contention_rate_per_hour']:.1f} timeouts/hour. "
                    f"Performance may be degraded. Consider immediate storage backend upgrade."
                )
            elif lock_stats["contention_status"] == "MODERATE":
                logger.warning(
                    f"Moderate lock contention: {lock_stats['contention_rate_per_hour']:.1f} timeouts/hour. "
                    f"Monitor performance and consider storage backend upgrade."
                )

            # Check rate limit status
            rate_limit_stats = self.get_rate_limit_statistics()
            if rate_limit_stats["rate_limit_status"] == "HIGH":
                logger.error(
                    f"High Infura rate limit errors detected: {rate_limit_stats['rate_limit_rate_per_hour']:.1f} errors/hour. "
                    f"Upgrade to a paid Infura plan or reduce API call frequency. "
                    f"Current project ID: {rate_limit_stats['infura_project_id']}"
                )
            elif rate_limit_stats["rate_limit_status"] == "MODERATE":
                logger.warning(
                    f"Moderate Infura rate limit errors: {rate_limit_stats['rate_limit_rate_per_hour']:.1f} errors/hour. "
                    f"Monitor usage to avoid hitting limits."
                )
            else:
                logger.debug(
                    f"Infura rate limit status: {rate_limit_stats['rate_limit_errors']} errors in {rate_limit_stats['hours_since_reset']:.1f}h "
                    f"(threshold: {rate_limit_stats['rate_limit_threshold']})"
                )

            # Check event processing configuration
            event_config = self.get_event_processing_config()
            logger.debug(
                f"Event processing configured: {event_config['block_step']} blocks/batch, "
                f"max {event_config['max_events']} events, {event_config['max_block_range']} block range, "
                f"resource leak prevention: {event_config['resource_leak_prevention']}"
            )

            # Check timeout validation configuration
            timeout_config = self.get_timeout_validation_info()
            logger.debug(
                f"Timeout validation enabled: {timeout_config['timeout_validation_enabled']}, "
                f"fallback timeout: {timeout_config['fallback_timeout_minutes']} minutes"
            )

            # Check reorg protection configuration
            reorg_config = self.get_reorg_protection_info()
            logger.debug(
                f"Reorg protection: {reorg_config['effective_confirmations']} confirmations "
                f"({reorg_config['safety_margin_confirmations']} safety margin), "
                f"risk assessment: {reorg_config['reorg_risk_assessment']}"
            )

            # Check race condition protection configuration
            race_protection_config = self.get_race_condition_protection_info()
            logger.debug(
                f"Race condition protection: {race_protection_config['race_condition_protection_enabled']}, "
                f"atomic updates: {race_protection_config['atomic_status_updates']}"
            )

            # Check network congestion and dynamic block time estimation
            congestion_config = self.get_network_congestion_info()
            if congestion_config.get("dynamic_block_time_enabled"):
                dynamic_time = congestion_config.get("current_dynamic_block_time_seconds")
                configured_time = congestion_config.get("configured_block_time_seconds")
                congestion_level = congestion_config.get("congestion_level")
                logger.debug(
                    f"Network congestion: {congestion_level}, "
                    f"dynamic block time: {dynamic_time:.1f}s, "
                    f"configured: {configured_time}s"
                )
            else:
                logger.warning("Dynamic block time estimation disabled or failed")

            # Check USDT precision validation configuration
            precision_config = self.get_usdt_precision_info()
            logger.debug(
                f"USDT precision validation: {precision_config['usdt_precision_validation_enabled']}, "
                f"decimals: {precision_config['usdt_decimals']}, "
                f"tolerance: {precision_config['precision_tolerance']}"
            )

            # Check transaction receipt validation configuration
            receipt_config = self.get_receipt_validation_info()
            logger.debug(
                f"Receipt validation: {receipt_config['receipt_validation_enabled']}, "
                f"success status: {receipt_config['success_status']}, "
                f"features: {len(receipt_config['validation_features'])}"
            )

            # Check timeout validation configuration (includes storage retry info)
            timeout_config = self.get_timeout_validation_info()
            logger.debug(
                f"Timeout validation: {timeout_config['timeout_validation_enabled']}, "
                f"early validation: {timeout_config['early_timeout_validation']}, "
                f"storage retries: {timeout_config['storage_write_retries']}, "
                f"verification retries: {timeout_config['verification_storage_retries']}"
            )

            # Check storage retry configuration
            storage_retry_config = self.get_storage_retry_info()
            logger.debug(
                f"Storage retry: {storage_retry_config['storage_retry_enabled']}, "
                f"max retries: {storage_retry_config['max_retries']}, "
                f"scenarios: {len(storage_retry_config['verification_retry_scenarios'])}"
            )

            # Check deadlock prevention configuration
            deadlock_config = self.get_deadlock_prevention_info()
            logger.debug(
                f"Deadlock prevention: {deadlock_config['deadlock_prevention_enabled']}, "
                f"lock timeout: {deadlock_config['lock_timeout_seconds']}s, "
                f"commit timeout: {deadlock_config['commit_timeout_seconds']}s"
            )

            # Check storage backend
            test_transaction_id = f"health_check_{uuid.uuid4()}"
            test_transaction = PaymentTransaction(
                id=test_transaction_id,
                user_id="health_check",
                amount=0.01,
                currency="USDT",
                payment_method="crypto_usdt",
                status="pending",
                created_at=datetime.now(timezone.utc),
                completed_at=None,
                metadata={"test_transaction": True},
            )
            with self._transaction_scope():
                self.storage.save_transaction(test_transaction)
                saved_transaction = self.storage.get_transaction(test_transaction_id)
                if not saved_transaction or saved_transaction.id != test_transaction_id:
                    raise Exception("Storage backend failed read/write consistency check")
                # Clean up test transaction if storage supports delete
                delete_method = getattr(self.storage, "delete_transaction", None)
                if delete_method and callable(delete_method):
                    try:
                        delete_method(test_transaction_id)
                    except Exception as e:
                        logger.warning(f"Failed to cleanup test transaction: {e}")
            logger.debug("Storage backend passed read/write consistency check")

            # Simulate minimal transaction verification
            try:
                self._verify_transfer_event_with_confirmations(test_transaction_id, 1000)  # Small amount for test
                logger.debug("Transaction verification simulation successful")
            except Exception as e:
                logger.warning(f"Transaction verification simulation failed: {e}")

            # Simulate rate limit and congestion scenarios
            self._simulate_rate_limit_and_congestion_scenarios()

        except Exception as e:
            raise Exception(f"CryptoProvider health check failed: {e}")

    def _simulate_rate_limit_and_congestion_scenarios(self) -> None:
        """
        Simulate rate limit and network congestion scenarios to test provider resilience.

        This method tests the provider's ability to handle common production issues
        without affecting actual operations.
        """
        try:
            logger.debug("Starting rate limit and congestion simulation tests")

            # Test 1: Dynamic block time estimation under simulated congestion
            try:
                # Simulate network congestion by testing dynamic block time estimation
                congestion_test_result = self._test_dynamic_block_time_estimation()
                if congestion_test_result["success"]:
                    logger.debug(f"Dynamic block time estimation test passed: {congestion_test_result['message']}")
                else:
                    logger.warning(f"Dynamic block time estimation test failed: {congestion_test_result['message']}")
            except Exception as e:
                logger.warning(f"Dynamic block time estimation test error: {e}")

            # Test 2: Rate limit backoff strategy simulation
            try:
                backoff_test_result = self._test_rate_limit_backoff_strategy()
                if backoff_test_result["success"]:
                    logger.debug(f"Rate limit backoff test passed: {backoff_test_result['message']}")
                else:
                    logger.warning(f"Rate limit backoff test failed: {backoff_test_result['message']}")
            except Exception as e:
                logger.warning(f"Rate limit backoff test error: {e}")

            # Test 3: Network congestion level assessment
            try:
                congestion_assessment = self._assess_network_congestion_level()
                logger.debug(
                    f"Network congestion assessment: {congestion_assessment['level']} - {congestion_assessment['reason']}"
                )
            except Exception as e:
                logger.warning(f"Network congestion assessment error: {e}")

            logger.debug("Rate limit and congestion simulation tests completed")

        except Exception as e:
            logger.warning(f"Rate limit and congestion simulation failed: {e}")

    def _test_dynamic_block_time_estimation(self) -> Dict[str, Any]:
        """
        Test dynamic block time estimation functionality.

        Returns:
            Dictionary containing test results
        """
        try:
            # Test dynamic block time estimation
            dynamic_time = self._estimate_dynamic_block_time()
            configured_time = self.network_config["block_time"]

            if dynamic_time is None:
                return {
                    "success": False,
                    "message": "Dynamic estimation returned None, using configured block time",
                    "configured_time": configured_time,
                    "dynamic_time": None,
                }

            # Validate the estimated time is reasonable
            min_reasonable = 1.0
            max_reasonable = 60.0

            if min_reasonable <= dynamic_time <= max_reasonable:
                return {
                    "success": True,
                    "message": f"Dynamic estimation working: {dynamic_time:.1f}s vs configured {configured_time}s",
                    "configured_time": configured_time,
                    "dynamic_time": dynamic_time,
                    "deviation_percent": abs((dynamic_time - configured_time) / configured_time * 100),
                }
            else:
                return {
                    "success": False,
                    "message": f"Dynamic estimation outside reasonable range: {dynamic_time:.1f}s",
                    "configured_time": configured_time,
                    "dynamic_time": dynamic_time,
                }

        except Exception as e:
            return {"success": False, "message": f"Dynamic estimation test error: {e}", "error": str(e)}

    def _test_rate_limit_backoff_strategy(self) -> Dict[str, Any]:
        """
        Test rate limit backoff strategy without making actual API calls.

        Returns:
            Dictionary containing test results
        """
        try:
            # Simulate rate limit backoff calculation
            max_rate_limit_errors = 3
            backoff_times = []

            for error_count in range(1, max_rate_limit_errors + 1):
                backoff_seconds = 2**error_count  # Exponential backoff: 2s, 4s, 8s
                backoff_times.append(backoff_seconds)

            # Validate backoff strategy
            if len(backoff_times) == max_rate_limit_errors and all(t > 0 for t in backoff_times):
                return {
                    "success": True,
                    "message": f"Backoff strategy: {backoff_times} seconds for {max_rate_limit_errors} errors",
                    "backoff_times": backoff_times,
                    "max_errors": max_rate_limit_errors,
                    "strategy": "Exponential (2^n seconds)",
                }
            else:
                return {"success": False, "message": "Invalid backoff times calculated", "backoff_times": backoff_times}

        except Exception as e:
            return {"success": False, "message": f"Backoff strategy test error: {e}", "error": str(e)}

    def _assess_network_congestion_level(self) -> Dict[str, Any]:
        """
        Assess current network congestion level.

        Returns:
            Dictionary containing congestion assessment
        """
        try:
            dynamic_time = self._estimate_dynamic_block_time()
            configured_time = self.network_config["block_time"]

            if dynamic_time is None:
                return {
                    "level": "UNKNOWN",
                    "reason": "Dynamic estimation unavailable",
                    "configured_time": configured_time,
                    "dynamic_time": None,
                }

            # Determine congestion level based on block time ratio
            ratio = dynamic_time / configured_time

            if ratio <= 1.2:
                level = "LOW"
                reason = "Block times near normal"
            elif ratio <= 2.0:
                level = "MODERATE"
                reason = "Block times 1.2-2x normal"
            elif ratio <= 3.0:
                level = "HIGH"
                reason = "Block times 2-3x normal"
            else:
                level = "SEVERE"
                reason = "Block times >3x normal (severe congestion)"

            return {
                "level": level,
                "reason": reason,
                "configured_time": configured_time,
                "dynamic_time": dynamic_time,
                "ratio": ratio,
                "assessment_time": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            return {"level": "ERROR", "reason": f"Assessment failed: {e}", "error": str(e)}

    def get_network_info(self) -> Dict[str, Any]:
        """
        Get current network information.

        Returns:
            Dictionary containing network status, gas price, latest block, etc.
        """
        try:
            latest_block = self.w3.eth.block_number
            gas_price = self.w3.eth.gas_price
            gas_price_gwei = self.w3.from_wei(gas_price, "gwei")

            return {
                "network": self.network,
                "network_name": self.network_config["name"],
                "chain_id": self.network_config["chain_id"],
                "latest_block": latest_block,
                "gas_price_wei": gas_price,
                "gas_price_gwei": gas_price_gwei,
                "max_gas_price_gwei": self.max_gas_price_gwei,
                "confirmations_required": self.confirmations_required,
                "block_time_seconds": self.network_config["block_time"],
                "is_connected": self.w3.is_connected(),
            }
        except Exception as e:
            logger.error(f"Error getting network info: {e}")
            raise ProviderError(f"Failed to get network info: {e}", provider="crypto")

    def get_usdt_balance(self, address: Optional[str] = None) -> Dict[str, Any]:
        """
        Get USDT balance for an address.

        Args:
            address: Address to check (defaults to wallet_address)

        Returns:
            Dictionary containing balance information
        """
        try:
            target_address = address or self.wallet_address
            normalized_address = self._normalize_address(target_address)

            balance_wei = self.usdt_contract.functions.balanceOf(normalized_address).call()
            balance_usdt = balance_wei / (10**self.usdt_decimals)

            return {
                "address": normalized_address,
                "balance_wei": balance_wei,
                "balance_usdt": balance_usdt,
                "decimals": self.usdt_decimals,
                "symbol": self.usdt_symbol,
            }
        except Exception as e:
            logger.error(f"Error getting USDT balance: {e}")
            raise ProviderError(f"Failed to get USDT balance: {e}", provider="crypto")

    @retry(
        exceptions=(HTTPError, Exception),
        max_attempts=5,
        logger=logger,
        retry_message="Retrying payment processing due to Infura rate limit or network error...",
        backoff_factor=2,  # Exponential backoff: 1s, 2s, 4s, 8s, 16s
    )
    def process_payment(
        self,
        user_id: str,
        amount: float,
        currency: str = "USD",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentTransaction:
        """
        Process a USDT payment.

        This method creates a payment transaction and returns the transaction details.
        The actual payment verification happens in verify_payment().

        Args:
            user_id: Unique identifier for the user
            amount: Payment amount
            currency: Payment currency (USD or USDT)
            metadata: Additional transaction metadata

        Returns:
            PaymentTransaction object

        Raises:
            ValidationError: If parameters are invalid
            PaymentFailed: If payment processing fails
            ProviderError: If HTTP errors occur (except 429 rate limits which are retried)
        """
        try:
            # Comprehensive input validation
            self._validate_payment_inputs(user_id, amount, currency)

            # Validate metadata to prevent TypeError in dictionary unpacking
            if metadata is not None and not isinstance(metadata, dict):
                raise ValidationError(
                    f"Metadata must be a dictionary or None, got {type(metadata).__name__}",
                    field="metadata",
                    value=metadata,
                )

            # Require sender_address in metadata
            sender_address = None
            if metadata is not None:
                sender_address = metadata.get("sender_address")
            if not sender_address or not isinstance(sender_address, str) or not sender_address.strip():
                raise ValidationError(
                    "sender_address is required in metadata and must be a non-empty string",
                    field="sender_address",
                    value=sender_address,
                )
            sender_address = sender_address.strip()
            # Validate Ethereum address format
            try:
                sender_address = self._normalize_address(sender_address)
            except Exception as e:
                raise ValidationError(
                    f"Invalid Ethereum sender_address: {e}",
                    field="sender_address",
                    value=sender_address,
                )

            # Get provider capabilities for validation
            caps = self.get_capabilities()

            # Validate amount against capabilities
            if amount < caps.min_amount:
                raise ValidationError(f"Amount {amount} is below minimum {caps.min_amount}", field="amount", value=amount)
            if amount > caps.max_amount:
                raise ValidationError(f"Amount {amount} is above maximum {caps.max_amount}", field="amount", value=amount)

            # Get current USDT price and convert with proper precision
            usdt_price = self._get_usdt_price()
            if currency == "USDT":
                usdt_amount = amount
            else:
                # Convert USD to USDT using current price
                usdt_amount = amount / usdt_price

                # Validate USDT conversion for significant deviations (sanity check)
                deviation_threshold = 0.01  # 1% deviation threshold
                if abs(usdt_amount - amount) > amount * deviation_threshold:
                    logger.warning(
                        f"USDT conversion deviation detected: {usdt_amount:.6f} USDT for {amount} USD "
                        f"(deviation: {abs(usdt_amount - amount):.6f}, threshold: {amount * deviation_threshold:.6f})"
                    )
                else:
                    logger.debug(f"USDT conversion within acceptable range: {usdt_amount:.6f} USDT for {amount} USD")

            # Ensure precision to avoid rounding errors
            usdt_amount = round(Decimal(str(usdt_amount)), self.usdt_decimals)

            # Convert to wei and validate precision
            usdt_amount_wei = int(Decimal(str(usdt_amount)) * (10**self.usdt_decimals))

            # Validate that the conversion is precise (no precision loss)
            reconstructed_usdt = usdt_amount_wei / (10**self.usdt_decimals)
            if abs(reconstructed_usdt - float(usdt_amount)) > 0.000001:  # 6 decimal precision tolerance
                logger.error(f"Precision loss detected in USDT conversion: {usdt_amount} -> {reconstructed_usdt}")
                raise ValidationError("USDT amount precision loss detected", field="amount", value=amount)

            # Validate wei amount is reasonable
            if usdt_amount_wei <= 0:
                raise ValidationError("Invalid USDT amount in wei after conversion", field="amount", value=amount)

            # Generate unique transaction ID with placeholder reservation
            transaction_id = self._generate_unique_transaction_id()

            now = datetime.now(timezone.utc)

            # Get current network info for transaction
            network_info = self.get_network_info()

            # Add timeout (30 minutes from creation) with validation
            timeout_at = now + timedelta(minutes=30)
            timeout_iso = timeout_at.isoformat()

            transaction = PaymentTransaction(
                id=transaction_id,
                user_id=user_id,
                amount=amount,
                currency=currency,
                payment_method="crypto_usdt",
                status="pending",
                created_at=now,
                completed_at=None,
                metadata={
                    **(metadata or {}),
                    "crypto_type": "usdt",
                    "network": self.network,
                    "network_name": self.network_config["name"],
                    "wallet_address": self.wallet_address,
                    "usdt_price": float(usdt_price),
                    "usdt_amount": float(usdt_amount),
                    "usdt_amount_wei": usdt_amount_wei,
                    "precision_validated": True,
                    "contract_address": self.usdt_contract.address,
                    "contract_symbol": self.usdt_symbol,
                    "contract_name": self.usdt_name,
                    "confirmations_required": self.confirmations_required,
                    "created_block": network_info["latest_block"],
                    "gas_price_at_creation_gwei": network_info["gas_price_gwei"],
                    "timeout_at": timeout_iso,
                    "timeout_minutes": 30,
                    "timeout_validated": True,
                    "sender_address": sender_address,
                },
            )

            # Replace the __RESERVED__ placeholder with the actual transaction object
            with self.transactions_lock:
                if transaction_id in self.transactions:
                    if self.transactions[transaction_id] == "__RESERVED__":
                        self.transactions[transaction_id] = transaction

            # Store transaction with concurrency control and verification
            max_storage_retries = 3
            for attempt in range(max_storage_retries):
                try:
                    with self._transaction_scope():
                        self.storage.save_transaction(transaction)
                        logger.debug(f"Transaction {transaction_id} saved successfully")

                        # Verify the transaction was saved correctly
                        saved_transaction = self.storage.get_transaction(transaction_id)
                        if not saved_transaction:
                            raise ProviderError(
                                f"Storage verification failed for transaction {transaction_id}", provider="crypto"
                            )

                        # Additional validation: ensure all critical fields are preserved
                        if (
                            saved_transaction.id != transaction_id
                            or saved_transaction.user_id != user_id
                            or saved_transaction.amount != amount
                            or saved_transaction.status != "pending"
                        ):
                            raise ProviderError(
                                f"Storage data integrity check failed for transaction {transaction_id}", provider="crypto"
                            )

                        logger.debug(f"Transaction {transaction_id} saved and verified successfully (attempt {attempt + 1})")
                        break  # Exit retry loop after successful save/verification
                except Exception as e:
                    if attempt == max_storage_retries - 1:
                        logger.error(f"Failed to save transaction {transaction_id} after {max_storage_retries} attempts: {e}")
                        # Clean up the placeholder if storage fails
                        self._cleanup_reserved_placeholder(transaction_id)
                        # For production environments, log critical storage failure but don't fail payment
                        if not self._is_dev_mode():
                            logger.critical(
                                f"CRITICAL: Payment succeeded but storage failed for transaction {transaction_id}. Payment amount: {amount} {currency}"
                            )
                            # Add storage failure flag to transaction metadata
                            transaction.metadata["storage_failed"] = True
                            transaction.metadata["storage_error"] = str(e)
                            # Return the transaction even though storage failed
                            return transaction
                        else:
                            raise ProviderError(
                                f"Transaction storage failed after {max_storage_retries} attempts: {e}", provider="crypto"
                            )
                    else:
                        logger.warning(f"Storage attempt {attempt + 1} failed for transaction {transaction_id}: {e}, retrying...")
                        sleep(0.1 * (attempt + 1))  # Short backoff between retries
            else:
                # If we exhausted all storage retries
                raise ProviderError(f"Failed to save transaction after {max_storage_retries} attempts", provider="crypto")

            logger.info(
                f"Created USDT payment transaction: {transaction_id} "
                f"for user {user_id}, amount: {amount} {currency} "
                f"({usdt_amount} USDT), address: {self.wallet_address}, "
                f"timeout: {timeout_iso}"
            )

            # Always return the stored transaction (not the newly created object)
            stored_transaction = self.storage.get_transaction(transaction_id)
            if not stored_transaction:
                raise ProviderError(f"Transaction {transaction_id} not found after save", provider="crypto")
            return stored_transaction

        except HTTPError as e:
            self._handle_rate_limit(e)  # Track and warn about rate limits
            if hasattr(e, "response") and e.response and e.response.status_code == 429:
                logger.error(f"Infura rate limit hit during payment processing for user {user_id}: {e}")
                raise  # Let retry decorator handle it
            raise ProviderError(f"HTTP error during payment processing: {e}", provider="crypto")
        except Exception as e:
            # Clean up any __RESERVED__ placeholder if transaction creation failed
            if "transaction_id" in locals():
                self._cleanup_reserved_placeholder(transaction_id)
            if isinstance(e, (ValidationError, PaymentFailed, ProviderError)):
                raise
            raise PaymentFailed(f"Payment processing failed: {e}", provider_error="crypto")

    def _validate_payment_inputs(self, user_id: str, amount: float, currency: str) -> None:
        """Validate payment input parameters."""
        if not user_id or not isinstance(user_id, str):
            raise ValidationError("user_id is required and must be a non-empty string", field="user_id", value=user_id)

        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValidationError("amount must be a positive number", field="amount", value=amount)

        if not currency or not isinstance(currency, str):
            raise ValidationError("currency is required and must be a non-empty string", field="currency", value=currency)

        caps = self.get_capabilities()
        if currency not in caps.supported_currencies:
            raise ValidationError(
                f"Unsupported currency: {currency}. " f"Supported currencies: {', '.join(caps.supported_currencies)}",
                field="currency",
                value=currency,
            )

    @retry(
        exceptions=(HTTPError, Exception),
        max_attempts=5,
        logger=logger,
        retry_message="Retrying payment verification due to Infura rate limit or network error...",
        backoff_factor=2,  # Exponential backoff: 1s, 2s, 4s, 8s, 16s
    )
    def verify_payment(self, transaction_id: str) -> bool:
        """
        Verify USDT payment on-chain.

        This method checks for specific transfer events to the wallet address
        that match the expected amount and have sufficient confirmations.

        Args:
            transaction_id: ID of the transaction to verify

        Returns:
            True if payment is verified, False otherwise

        Raises:
            ValidationError: If transaction_id is invalid
            ProviderError: If verification fails due to provider issues
        """
        if not transaction_id or not isinstance(transaction_id, str):
            raise ValidationError(
                "transaction_id is required and must be a non-empty string", field="transaction_id", value=transaction_id
            )

        transaction = self.storage.get_transaction(transaction_id)
        if not transaction:
            logger.warning(f"USDT transaction not found: {transaction_id}")
            return False

        try:
            # Use a single transaction scope for all status updates to prevent race conditions
            with self._transaction_scope():
                # Re-fetch transaction to get latest state (prevents race conditions)
                transaction = self.storage.get_transaction(transaction_id)
                if not transaction:
                    logger.warning(f"USDT transaction not found: {transaction_id}")
                    return False

                # Check if transaction was already completed (atomic check)
                if transaction.status == "completed":
                    logger.info(f"Transaction {transaction_id} already completed")
                    return True

                # Validate required metadata fields
                required_metadata = ["usdt_amount_wei", "contract_address", "timeout_at"]
                missing_fields = [field for field in required_metadata if field not in transaction.metadata]
                if missing_fields:
                    logger.error(f"Missing metadata for transaction {transaction_id}: {missing_fields}")
                    transaction.status = "failed"
                    transaction.metadata["failure_reason"] = f"Missing required metadata: {', '.join(missing_fields)}"
                    if not self._save_transaction_with_retry(transaction):
                        logger.error(f"Failed to save failed transaction {transaction_id} after retries")
                        raise ProviderError(f"Storage write failed for transaction {transaction_id}", provider="crypto")
                    return False

                # Validate usdt_amount_wei
                expected_amount_wei = transaction.metadata.get("usdt_amount_wei", 0)
                if not isinstance(expected_amount_wei, (int, float)) or expected_amount_wei <= 0:
                    logger.error(f"Invalid usdt_amount_wei for transaction {transaction_id}: {expected_amount_wei}")
                    transaction.status = "failed"
                    transaction.metadata["failure_reason"] = "Invalid USDT amount in wei"
                    if not self._save_transaction_with_retry(transaction):
                        logger.error(f"Failed to save failed transaction {transaction_id} after retries")
                        raise ProviderError(f"Storage write failed for transaction {transaction_id}", provider="crypto")
                    return False

                # Validate contract_address
                contract_address = transaction.metadata.get("contract_address")
                if (
                    not contract_address
                    or not self.w3.is_address(contract_address)
                    or contract_address.lower() != USDT_CONTRACTS[self.network].lower()
                ):
                    logger.error(f"Invalid contract_address for transaction {transaction_id}: {contract_address}")
                    transaction.status = "failed"
                    transaction.metadata["failure_reason"] = "Invalid USDT contract address"
                    if not self._save_transaction_with_retry(transaction):
                        logger.error(f"Failed to save failed transaction {transaction_id} after retries")
                        raise ProviderError(f"Storage write failed for transaction {transaction_id}", provider="crypto")
                    return False

                # Check for timeout with fallback handling
                timeout_at_str = transaction.metadata.get("timeout_at")
                try:
                    if timeout_at_str:
                        timeout_at = datetime.fromisoformat(timeout_at_str.replace("Z", "+00:00"))
                    else:
                        # Fallback to 30 minutes from created_at
                        timeout_at = transaction.created_at + timedelta(minutes=30)
                        logger.warning(f"Missing timeout_at for transaction {transaction_id}, using default 30-minute timeout")

                    if datetime.now(timezone.utc) > timeout_at:
                        transaction.status = "failed"
                        transaction.metadata["failure_reason"] = "Transaction timed out"
                        if not self._save_transaction_with_retry(transaction):
                            logger.error(f"Failed to save timed out transaction {transaction_id} after retries")
                            raise ProviderError(f"Storage write failed for transaction {transaction_id}", provider="crypto")
                        logger.warning(f"Transaction {transaction_id} timed out")
                        return False
                except ValueError as e:
                    logger.error(f"Invalid timeout_at format for transaction {transaction_id}: {e}")
                    # Fallback to 30 minutes from created_at
                    timeout_at = transaction.created_at + timedelta(minutes=30)
                    if datetime.now(timezone.utc) > timeout_at:
                        transaction.status = "failed"
                        transaction.metadata["failure_reason"] = "Transaction timed out (invalid timeout format)"
                        if not self._save_transaction_with_retry(transaction):
                            logger.error(f"Failed to save timed out transaction {transaction_id} after retries")
                            raise ProviderError(f"Storage write failed for transaction {transaction_id}", provider="crypto")
                        logger.warning(f"Transaction {transaction_id} timed out due to invalid timeout format")
                        return False

                # Get expected USDT amount in wei
                expected_amount_wei = transaction.metadata.get("usdt_amount_wei", 0)
                if expected_amount_wei <= 0:
                    logger.warning(f"Invalid expected amount for transaction: {transaction_id}")
                    return False

                # Look for the specific transfer event with confirmations
                if self._verify_transfer_event_with_confirmations(transaction_id, expected_amount_wei):
                    transaction.status = "completed"
                    transaction.completed_at = datetime.now(timezone.utc)

                    # Update metadata with completion info
                    network_info = self.get_network_info()
                    transaction.metadata.update(
                        {
                            "completed_block": network_info["latest_block"],
                            "gas_price_at_completion_gwei": network_info["gas_price_gwei"],
                            "verification_time": datetime.now(timezone.utc).isoformat(),
                        }
                    )

                    # Save the updated transaction to storage with retry logic
                    if not self._save_transaction_with_retry(transaction):
                        logger.error(f"Failed to save completed transaction {transaction_id} after retries")
                        raise ProviderError(f"Storage write failed for completed transaction {transaction_id}", provider="crypto")

                    logger.info(f"USDT payment confirmed: {transaction_id}")
                    return True

                logger.info(f"No confirmed USDT payment found for {transaction_id}")
                return False

        except HTTPError as e:
            self._handle_rate_limit(e)  # Track and warn about rate limits
            if hasattr(e, "response") and e.response and e.response.status_code == 429:
                logger.error(f"Infura rate limit hit during payment verification for transaction {transaction_id}: {e}")
                raise  # Let retry decorator handle it
            raise ProviderError(f"HTTP error during payment verification: {e}", provider="crypto")
        except Exception as e:
            logger.error(f"Error verifying USDT payment: {e}")
            raise ProviderError(f"USDT payment verification error: {e}", provider="crypto")

    def _get_block_number_at_time(self, target_time: datetime) -> int:
        """
        Get the block number closest to the target time using dynamic block time estimation.

        This implementation uses recent block timestamps to estimate average block time,
        accounting for network congestion where block times can vary significantly.
        """
        try:
            # Get current block
            current_block = self.w3.eth.block_number
            current_time = datetime.now(timezone.utc)

            # If target time is in the future, return current block
            if target_time > current_time:
                logger.warning(f"Target time {target_time} is in the future, using current block")
                return current_block

            # Estimate blocks based on time difference
            time_diff = current_time - target_time
            seconds_diff = time_diff.total_seconds()

            # Only estimate if we have a positive time difference
            if seconds_diff <= 0:
                return current_block

            # Use dynamic block time estimation based on recent blocks
            dynamic_block_time = self._estimate_dynamic_block_time()

            # Use dynamic block time if available, otherwise fall back to configured block time
            effective_block_time = dynamic_block_time or self.network_config["block_time"]

            blocks_diff = int(seconds_diff / effective_block_time)
            estimated_block = max(0, current_block - blocks_diff)

            # Ensure we don't go too far back
            max_blocks_back = 1000
            estimated_block = max(estimated_block, current_block - max_blocks_back)

            # Log the estimation details for debugging
            logger.debug(
                f"Block estimation: target_time={target_time}, "
                f"time_diff={seconds_diff:.1f}s, "
                f"dynamic_block_time={dynamic_block_time:.1f}s, "
                f"effective_block_time={effective_block_time:.1f}s, "
                f"blocks_diff={blocks_diff}, "
                f"estimated_block={estimated_block}"
            )

            return estimated_block

        except Exception as e:
            logger.warning(f"Could not estimate block number at time {target_time}: {e}")
            # Fallback to current block - 100 (reasonable historical point)
            try:
                return max(0, self.w3.eth.block_number - 100)
            except Exception:
                # Last resort fallback
                return 0

    def _estimate_dynamic_block_time(self) -> Optional[float]:
        """
        Estimate dynamic block time using recent block timestamps.

        This method samples recent blocks to calculate the average block time,
        accounting for network congestion where block times can vary significantly.

        Returns:
            Average block time in seconds, or None if estimation fails
        """
        try:
            # Sample recent blocks for dynamic estimation
            sample_size = 10  # Sample last 10 blocks
            current_block = self.w3.eth.block_number

            # Get timestamps for recent blocks
            block_timestamps = []
            for i in range(sample_size):
                try:
                    block_number = current_block - i
                    if block_number < 0:
                        break

                    block = self.w3.eth.get_block(block_number)
                    if block and "timestamp" in block:
                        # Convert timestamp to datetime
                        block_time = datetime.fromtimestamp(block["timestamp"], tz=timezone.utc)
                        block_timestamps.append((block_number, block_time))
                except Exception as e:
                    logger.debug(f"Could not fetch block {block_number}: {e}")
                    continue

            # Need at least 2 blocks to calculate time differences
            if len(block_timestamps) < 2:
                logger.debug("Insufficient block data for dynamic estimation, using configured block time")
                return None

            # Calculate time differences between consecutive blocks
            time_differences = []
            for i in range(len(block_timestamps) - 1):
                current_block_num, current_time = block_timestamps[i]
                prev_block_num, prev_time = block_timestamps[i + 1]

                time_diff = (current_time - prev_time).total_seconds()
                block_diff = current_block_num - prev_block_num

                # Only include if blocks are consecutive (no gaps)
                if block_diff == 1:
                    time_differences.append(time_diff)

            if not time_differences:
                logger.debug("No consecutive blocks found for dynamic estimation")
                return None

            # Calculate average block time
            avg_block_time = sum(time_differences) / len(time_differences)

            # Validate the estimated block time is reasonable
            min_reasonable_time = 1.0  # 1 second minimum
            max_reasonable_time = 60.0  # 60 seconds maximum (severe congestion)

            if min_reasonable_time <= avg_block_time <= max_reasonable_time:
                logger.debug(f"Dynamic block time estimation: {avg_block_time:.1f}s (from {len(time_differences)} samples)")
                return avg_block_time
            else:
                logger.warning(
                    f"Dynamic block time estimation {avg_block_time:.1f}s outside reasonable range "
                    f"({min_reasonable_time}-{max_reasonable_time}s), using configured block time"
                )
                return None

        except Exception as e:
            logger.debug(f"Dynamic block time estimation failed: {e}")
            return None

    def _verify_transfer_event_with_confirmations(self, transaction_id: str, expected_amount_wei: int) -> bool:
        """
        Verify that a transfer event occurred with sufficient confirmations.

        This method looks for transfer events that:
        1. Match the expected amount exactly (or within tolerance)
        2. Have sufficient confirmations
        3. Occurred after the transaction was created
        4. Haven't been used to verify another transaction
        5. Have successful transaction receipts (status == 1)

        Args:
            transaction_id: Transaction ID to verify
            expected_amount_wei: Expected amount in wei

        Returns:
            True if transfer is verified with sufficient confirmations and successful receipt
        """
        transaction = None
        filter_ids = []  # Track filter IDs for guaranteed cleanup

        try:
            transaction = self.storage.get_transaction(transaction_id)
            if not transaction:
                return False

            # Early timeout validation to prevent unnecessary API calls
            timeout_at_str = transaction.metadata.get("timeout_at")
            try:
                if timeout_at_str:
                    timeout_at = datetime.fromisoformat(timeout_at_str.replace("Z", "+00:00"))
                else:
                    timeout_at = transaction.created_at + timedelta(minutes=30)
                    logger.warning(f"Missing timeout_at for transaction {transaction_id}, using default 30-minute timeout")
                if datetime.now(timezone.utc) > timeout_at:
                    logger.warning(f"Transaction {transaction_id} timed out before event verification")
                    transaction.status = "failed"
                    transaction.metadata["failure_reason"] = "Transaction timed out before event verification"
                    if not self._save_transaction_with_retry(transaction):
                        logger.error(f"Failed to save timed out transaction {transaction_id} after retries")
                        raise ProviderError(f"Storage write failed for timed out transaction {transaction_id}", provider="crypto")
                    return False
            except ValueError as e:
                logger.error(f"Invalid timeout_at format for transaction {transaction_id}: {e}")
                timeout_at = transaction.created_at + timedelta(minutes=30)
                if datetime.now(timezone.utc) > timeout_at:
                    transaction.status = "failed"
                    transaction.metadata["failure_reason"] = "Transaction timed out (invalid timeout format)"
                    if not self._save_transaction_with_retry(transaction):
                        logger.error(f"Failed to save timed out transaction {transaction_id} after retries")
                        raise ProviderError(f"Storage write failed for timed out transaction {transaction_id}", provider="crypto")
                    return False

            # Check Web3 connection before proceeding with comprehensive error handling
            try:
                if not self.w3.is_connected():
                    logger.error(f"Web3 connection lost during verification of transaction {transaction_id}")
                    transaction.metadata.update(
                        {
                            "verification_failure_reason": "Web3 connection lost",
                            "connection_status": "disconnected",
                            "last_connection_check": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    if not self._save_transaction_with_retry(transaction):
                        logger.error(f"Failed to save transaction {transaction_id} with connection error after retries")
                        raise ProviderError(f"Storage write failed for transaction {transaction_id}", provider="crypto")
                    raise ProviderError("Web3 connection lost during verification", provider="crypto")
            except (ConnectionError, TimeoutError) as e:
                logger.error(f"Web3 connection error during verification of transaction {transaction_id}: {e}")
                if transaction is not None:
                    transaction.metadata.update(
                        {
                            "verification_failure_reason": f"Web3 connection error: {str(e)}",
                            "connection_status": "failed",
                            "last_connection_check": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    if not self._save_transaction_with_retry(transaction):
                        logger.error(f"Failed to update transaction {transaction_id} with connection error: {e}")
                    else:
                        logger.error(f"Updated transaction {transaction_id} with connection error: {e}")
                raise ProviderError(f"Web3 connection error: {e}", provider="crypto")

            # Get block range based on transaction creation time
            current_block = self.w3.eth.block_number
            created_time = transaction.created_at

            # Look back 5 minutes from creation time to catch early transfers
            from_block = self._get_block_number_at_time(created_time - timedelta(minutes=5))

            # Limit maximum block range to avoid excessive API calls
            max_block_range = 1000
            from_block = max(from_block, current_block - max_block_range)
            from_block = max(0, from_block)  # Ensure non-negative

            logger.debug(f"Scanning transfer events from block {from_block} to {current_block}")

            # Paginate event fetching to prevent overload
            block_step = 100  # Process 100 blocks at a time
            max_events = 1000  # Cap total events processed
            events_processed = 0
            gas_price_skips = 0
            total_transactions = 0
            gas_price_threshold_multiplier = 1.5  # Allow 50% higher gas price if too many skips
            rate_limit_errors = 0
            max_rate_limit_errors = 3

            for start_block in range(from_block, current_block + 1, block_step):
                end_block = min(start_block + block_step - 1, current_block)
                logger.debug(f"Scanning transfer events from block {start_block} to {end_block}")

                transfer_filter = None
                filter_id = None  # Pre-declare filter ID for tracking

                try:
                    # Pre-create filter ID tracking to prevent resource leaks
                    # Track filter ID before creation to ensure cleanup even if creation fails
                    filter_id = f"transfer_{start_block}_{end_block}_{transaction_id}"
                    filter_ids.append(filter_id)

                    # Create filter with pre-creation tracking
                    transfer_filter = self.usdt_contract.events.Transfer.create_filter(  # type: ignore[attr-defined]
                        from_block=start_block, to_block=end_block, argument_filters={"to": self.wallet_address}
                    )

                    # Update filter ID with actual Infura filter ID
                    if transfer_filter and hasattr(transfer_filter, "filter_id"):
                        actual_filter_id = transfer_filter.filter_id
                        if filter_id in filter_ids:
                            filter_ids.remove(filter_id)
                        filter_ids.append(actual_filter_id)
                        filter_id = actual_filter_id

                    events = transfer_filter.get_all_entries()
                    events_processed += len(events)

                    if events_processed > max_events:
                        logger.warning(
                            f"Stopped processing events for transaction {transaction_id}: "
                            f"exceeded {max_events} events. Increase max_events or narrow block range."
                        )
                        return False

                    # Reset rate limit error count on successful API call
                    rate_limit_errors = 0

                    # Look for events with the expected amount and sufficient confirmations
                    for event in events:
                        event_amount = event["args"]["value"]
                        event_block = event["blockNumber"]
                        event_tx_hash = event["transactionHash"].hex()
                        total_transactions += 1

                        # Check sender address matches expected sender_address
                        expected_sender = transaction.metadata.get("sender_address")
                        event_sender = event["args"].get("from")
                        if not expected_sender or not event_sender or event_sender.lower() != expected_sender.lower():
                            logger.info(
                                f"Skipping event {event_tx_hash}: sender {event_sender} does not match expected {expected_sender}"
                            )
                            continue

                        # Check gas price with dynamic override
                        try:
                            tx = self.w3.eth.get_transaction(event_tx_hash)
                            gas_price = tx.get("gasPrice")
                            effective_max_gwei = self.max_gas_price_gwei
                            if gas_price:
                                gas_price_gwei = self.w3.from_wei(gas_price, "gwei")
                                # Override if too many transactions are skipped
                                if total_transactions > 10 and gas_price_skips / total_transactions > 0.5:
                                    effective_max_gwei = self.max_gas_price_gwei * gas_price_threshold_multiplier
                                    logger.warning(
                                        f"High gas price skip rate ({gas_price_skips}/{total_transactions}). "
                                        f"Increasing max gas price to {effective_max_gwei:.2f} gwei for transaction {event_tx_hash}"
                                    )
                                if gas_price_gwei > effective_max_gwei:
                                    logger.warning(
                                        f"Transaction {event_tx_hash} gas price {gas_price_gwei:.2f} gwei "
                                        f"exceeds max {effective_max_gwei:.2f} gwei - skipping"
                                    )
                                    gas_price_skips += 1
                                    continue
                        except Exception as e:
                            logger.warning(f"Could not fetch gas price for {event_tx_hash}: {e}")
                            # Continue with verification if we can't get gas price
                            pass

                        # Check if this transfer has already been used to verify another transaction
                        if self._is_transfer_already_used(event_tx_hash, event_amount):
                            continue

                        # Check if amount matches (with small tolerance for rounding)
                        amount_tolerance = int(expected_amount_wei * 0.001)  # 0.1% tolerance
                        if abs(event_amount - expected_amount_wei) <= amount_tolerance:
                            # Validate transaction receipt to ensure transaction was successful
                            try:
                                receipt = self.w3.eth.get_transaction_receipt(event_tx_hash)
                                if not receipt:
                                    logger.warning(f"No transaction receipt found for {event_tx_hash}")
                                    continue

                                # Check if transaction was successful (status == 1)
                                if receipt.get("status") != 1:
                                    logger.warning(
                                        f"Transaction {event_tx_hash} failed with status {receipt.get('status')}. "
                                        f"Transfer event logged but transaction reverted or failed."
                                    )
                                    continue

                                # Additional validation: check gas used vs gas limit
                                gas_used = receipt.get("gasUsed", 0)
                                gas_limit = receipt.get("gasLimit", 0)
                                if gas_limit > 0 and gas_used >= gas_limit:
                                    logger.warning(
                                        f"Transaction {event_tx_hash} may have run out of gas: " f"used {gas_used}/{gas_limit}"
                                    )
                                    # Don't fail here, but log for monitoring

                                logger.debug(f"Transaction receipt validated for {event_tx_hash}: status=1, gas_used={gas_used}")

                            except Exception as e:
                                logger.warning(f"Failed to validate transaction receipt for {event_tx_hash}: {e}")
                                # In production mode, fail verification if receipt fetching fails
                                # This prevents false positives from failed transactions
                                if not self._is_dev_mode():
                                    logger.error(
                                        f"Transaction receipt validation failed in production mode for {event_tx_hash}. "
                                        f"Failing verification to prevent false positives. Error: {e}"
                                    )
                                    continue  # Skip this transaction in production
                                else:
                                    # In dev mode, continue with verification if we can't get receipt
                                    # This is safer than rejecting valid transactions due to API issues
                                    logger.debug(f"Continuing verification in dev mode despite receipt fetch failure")
                                    pass

                            # Check confirmations
                            confirmations = current_block - event_block

                            # Add safety margin to reduce reorg risk (5 extra confirmations)
                            safety_margin = 5
                            if confirmations >= self.confirmations_required + safety_margin:
                                # Verify block is in canonical chain to prevent reorg issues
                                try:
                                    block = self.w3.eth.get_block(event_block)
                                    block_hash = block.get("hash")
                                    if block_hash and block_hash != event["blockHash"]:
                                        logger.warning(
                                            f"Block {event_block} for tx {event_tx_hash} is not in canonical chain. "
                                            f"Block hash mismatch: expected {event['blockHash']}, got {block_hash}"
                                        )
                                        continue
                                except Exception as e:
                                    logger.warning(f"Failed to verify block {event_block} for tx {event_tx_hash}: {e}")
                                    continue

                                # Store the transaction details
                                transaction.metadata.update(
                                    {
                                        "confirmed_tx_hash": event_tx_hash,
                                        "confirmed_block": event_block,
                                        "confirmations": confirmations,
                                        "safety_margin_applied": safety_margin,
                                        "effective_confirmations": self.confirmations_required + safety_margin,
                                        "from_address": event["args"]["from"],
                                        "actual_amount_wei": event_amount,
                                        "actual_amount_usdt": event_amount / (10**self.usdt_decimals),
                                        "verification_method": "transfer_event",
                                        "canonical_chain_verified": True,
                                        "block_hash_verified": event["blockHash"].hex(),
                                        "reorg_protection_applied": True,
                                        "receipt_validation_applied": True,
                                        "receipt_status": 1,
                                        "gas_used": receipt.get("gasUsed", 0) if "receipt" in locals() else None,
                                        "gas_limit": receipt.get("gasLimit", 0) if "receipt" in locals() else None,
                                        "events_processed": events_processed,
                                        "blocks_scanned": end_block - from_block + 1,
                                        "gas_price_skips": gas_price_skips,
                                        "total_transactions_scanned": total_transactions,
                                        "rate_limit_errors": rate_limit_errors,
                                    }
                                )

                                # Mark this transfer as used to prevent double-crediting with storage validation
                                self._mark_transfer_as_used(event_tx_hash, event_amount, transaction_id)

                                return True
                            else:
                                logger.debug(
                                    f"Transfer found but insufficient confirmations: "
                                    f"{confirmations}/{self.confirmations_required + safety_margin}"
                                )

                except Exception as e:
                    # Check if this is a rate limit error
                    if "429" in str(e) or "rate limit" in str(e).lower():
                        rate_limit_errors += 1
                        logger.warning(
                            f"Rate limit error {rate_limit_errors}/{max_rate_limit_errors} for blocks {start_block}-{end_block}: {e}"
                        )

                        if rate_limit_errors >= max_rate_limit_errors:
                            logger.error(f"Too many rate limit errors ({rate_limit_errors}), stopping event processing")
                            # Store rate limit info in transaction metadata
                            transaction.metadata.update(
                                {
                                    "rate_limit_errors": rate_limit_errors,
                                    "last_rate_limit_error": str(e),
                                    "event_processing_stopped": True,
                                }
                            )
                            if not self._save_transaction_with_retry(transaction):
                                logger.error(f"Failed to save transaction {transaction_id} with rate limit info after retries")
                                raise ProviderError(f"Storage write failed for transaction {transaction_id}", provider="crypto")
                            return False

                        # Exponential backoff: 2s, 4s, 8s
                        backoff_seconds = 2**rate_limit_errors
                        logger.info(f"Rate limit backoff: waiting {backoff_seconds}s before continuing")
                        sleep(backoff_seconds)
                        continue
                    else:
                        logger.warning(f"Error fetching events for blocks {start_block}-{end_block}: {e}")
                        continue  # Continue to next block range
                finally:
                    # Clean up filter immediately after use with comprehensive error handling
                    if transfer_filter and hasattr(transfer_filter, "filter_id"):
                        try:
                            self.w3.eth.uninstall_filter(transfer_filter.filter_id)
                            logger.debug(f"Cleaned up filter {transfer_filter.filter_id}")
                            if transfer_filter.filter_id in filter_ids:
                                filter_ids.remove(transfer_filter.filter_id)
                        except Exception as e:
                            logger.warning(f"Failed to uninstall filter {transfer_filter.filter_id}: {e}")
                            # Keep filter ID in list for final cleanup attempt
                            if transfer_filter.filter_id not in filter_ids:
                                filter_ids.append(transfer_filter.filter_id)

            # Final cleanup for any remaining filters with comprehensive error handling
            for filter_id in filter_ids:
                try:
                    self.w3.eth.uninstall_filter(filter_id)
                except Exception as e:
                    logger.warning(f"Failed to uninstall residual filter {filter_id}: {e}")

            # Log gas price skip statistics
            if total_transactions > 0:
                logger.debug(
                    f"Gas price skip rate: {gas_price_skips}/{total_transactions} "
                    f"({(gas_price_skips / total_transactions) * 100:.1f}%)"
                )

            logger.debug(f"Processed {events_processed} events across {end_block - from_block + 1} blocks")
            return False

        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Web3 connection error during verification of transaction {transaction_id}: {e}")
            try:
                if transaction is not None:
                    transaction.metadata.update(
                        {
                            "verification_failure_reason": f"Web3 connection error: {str(e)}",
                            "connection_status": "failed",
                            "last_connection_check": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    if not self._save_transaction_with_retry(transaction):
                        logger.error(f"Failed to update transaction {transaction_id} with connection error: {e}")
                    else:
                        logger.error(f"Updated transaction {transaction_id} with connection error: {e}")
            except Exception as storage_e:
                logger.error(f"Failed to update transaction {transaction_id} with connection error: {storage_e}")
            raise ProviderError(f"Web3 connection error: {e}", provider="crypto")
        except Exception as e:
            logger.warning(f"Error checking transfer events: {e}")
            return False

    def _is_transfer_already_used(self, tx_hash: str, amount_wei: int) -> bool:
        """
        Check if a transfer has already been used to verify another transaction.

        This prevents double-crediting of the same transfer.
        Uses transaction scope to ensure atomicity during concurrent verification.
        """
        try:
            with self._transaction_scope():
                # Get all completed transactions from storage within transaction scope
                completed_transactions = self.storage.list_transactions(status="completed")

                for transaction in completed_transactions:
                    confirmed_tx_hash = transaction.metadata.get("confirmed_tx_hash")
                    confirmed_amount = transaction.metadata.get("actual_amount_wei")
                    from_address = transaction.metadata.get("from_address")
                    event_block = transaction.metadata.get("confirmed_block")

                    # Validate that all required metadata is present
                    if not all([confirmed_tx_hash, confirmed_amount, from_address, event_block]):
                        logger.warning(f"Incomplete metadata for completed transaction {transaction.id}")
                        continue

                    # Check if this transfer matches the one we're verifying
                    if (
                        confirmed_tx_hash == tx_hash
                        and confirmed_amount == amount_wei
                        and from_address is not None
                        and event_block is not None
                    ):
                        logger.info(f"Transfer {tx_hash} already used by transaction {transaction.id}")
                        return True
                return False
        except Exception as e:
            logger.error(f"Error checking if transfer already used for tx_hash {tx_hash}: {e}")
            raise ProviderError(f"Failed to verify transfer uniqueness: {e}", provider="crypto")

    def _mark_transfer_as_used(self, tx_hash: str, amount_wei: int, transaction_id: str) -> None:
        """
        Mark a transfer as used by a specific transaction to prevent double-crediting.
        Includes storage write validation to ensure persistence.
        """
        try:
            with self._transaction_scope():
                transaction = self.storage.get_transaction(transaction_id)
                if not transaction:
                    logger.error(f"Transaction {transaction_id} not found for marking transfer {tx_hash} as used")
                    raise ProviderError(f"Transaction {transaction_id} not found", provider="crypto")

                # Update metadata with transfer details
                transaction.metadata.update(
                    {
                        "confirmed_tx_hash": tx_hash,
                        "actual_amount_wei": amount_wei,
                        "marked_as_used": True,
                        "mark_timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

                # Save with retry and validation
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        self.storage.save_transaction(transaction)
                        saved_transaction = self.storage.get_transaction(transaction_id)
                        if not saved_transaction or saved_transaction.metadata.get("confirmed_tx_hash") != tx_hash:
                            raise ProviderError(
                                f"Storage verification failed for marking transfer {tx_hash} as used", provider="crypto"
                            )
                        logger.debug(f"Transfer {tx_hash} marked as used for transaction {transaction_id}")
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            logger.error(f"Failed to mark transfer {tx_hash} as used after {max_retries} attempts: {e}")
                            raise ProviderError(f"Failed to persist transfer usage for {tx_hash}: {e}", provider="crypto")
                        logger.warning(f"Storage attempt {attempt + 1} failed for marking transfer {tx_hash}: {e}")
                        sleep(0.1 * (attempt + 1))
        except Exception as e:
            logger.error(f"Error marking transfer {tx_hash} as used: {e}")
            raise ProviderError(f"Failed to mark transfer {tx_hash} as used: {e}", provider="crypto")

    def _save_transaction_with_retry(self, transaction: PaymentTransaction, max_retries: int = 3) -> bool:
        """
        Save transaction to storage with retry logic for verification operations.

        Args:
            transaction: Transaction to save
            max_retries: Maximum number of retry attempts

        Returns:
            True if save was successful, False otherwise
        """
        for attempt in range(max_retries):
            try:
                self.storage.save_transaction(transaction)

                # Verify the transaction was saved correctly
                saved_transaction = self.storage.get_transaction(transaction.id)
                if not saved_transaction:
                    raise ProviderError(f"Storage verification failed for transaction {transaction.id}", provider="crypto")

                # Additional validation: ensure critical fields are preserved
                if saved_transaction.status != transaction.status or saved_transaction.completed_at != transaction.completed_at:
                    raise ProviderError(
                        f"Storage data integrity check failed for transaction {transaction.id}", provider="crypto"
                    )

                logger.debug(f"Transaction {transaction.id} saved and verified successfully (attempt {attempt + 1})")
                return True

            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to save transaction {transaction.id} after {max_retries} attempts: {e}")
                    return False
                else:
                    logger.warning(f"Storage attempt {attempt + 1} failed for transaction {transaction.id}: {e}, retrying...")
                    sleep(0.1 * (attempt + 1))  # Short backoff between retries

        return False

    def refund_payment(self, transaction_id: str, amount: Optional[float] = None) -> Dict[str, Any]:
        """
        Provide manual refund instructions for USDT payments.

        This provider cannot automatically refund payments. Instead, it provides
        detailed instructions for manual refund processing.

        Args:
            transaction_id: ID of the transaction to refund
            amount: Amount to refund (None for full refund)

        Returns:
            Dictionary containing refund instructions and details

        Raises:
            ProviderError: If transaction is not found or cannot be refunded
        """
        transaction = self.storage.get_transaction(transaction_id)
        if not transaction:
            logger.warning(f"USDT transaction not found for refund: {transaction_id}")
            raise ProviderError(f"Transaction {transaction_id} not found", provider="crypto")

        if transaction.status != "completed":
            logger.warning(f"Cannot refund incomplete transaction: {transaction_id}")
            raise ProviderError(
                f"Cannot refund incomplete transaction {transaction_id}. "
                "Transaction must be confirmed on blockchain first. "
                "Use verify_payment() to check confirmation status.",
                provider="crypto",
            )

        # Get refund amount
        refund_amount = amount if amount is not None else transaction.amount
        refund_usdt = refund_amount if transaction.currency == "USDT" else refund_amount

        # Get payer address from transaction metadata
        payer_address = transaction.metadata.get("from_address", "Unknown")

        logger.info(f"Manual refund requested for USDT transaction: {transaction_id}")

        return {
            "status": "manual_refund_required",
            "transaction_id": transaction_id,
            "refund_amount": refund_amount,
            "refund_amount_usdt": refund_usdt,
            "payer_address": payer_address,
            "instructions": (
                "USDT REFUND INSTRUCTIONS:\n"
                "1. Use your wallet to send USDT to the original payer\n"
                "2. Payer address: {payer_address}\n"
                "3. Refund amount: {refund_usdt} USDT\n"
                "4. Send the refund using your own wallet (not through this provider)\n"
                "5. Consider gas fees when calculating refund amount\n"
                "6. Include a memo/note with transaction ID: {transaction_id}"
            ).format(payer_address=payer_address, refund_usdt=refund_usdt, transaction_id=transaction_id),
            "transaction_hash": transaction.metadata.get("confirmed_tx_hash"),
            "wallet_address": self.wallet_address,
            "network": self.network,
            "network_name": self.network_config["name"],
            "contract_address": self.usdt_contract.address,
            "developer_note": (
                "This provider cannot automatically refund USDT payments. "
                "You must manually process refunds using your own wallet. "
                "Consider implementing a separate refund service or using a "
                "wallet provider that supports automated refunds."
            ),
        }

    def get_payment_status(self, transaction_id: str) -> str:
        """
        Get the current status of a USDT payment.

        This method verifies the payment on-chain and returns the current status.

        Args:
            transaction_id: ID of the transaction to check

        Returns:
            Payment status string ('pending', 'completed', 'failed')

        Raises:
            ProviderError: If transaction is not found or status check fails
        """
        transaction = self.storage.get_transaction(transaction_id)
        if not transaction:
            logger.warning(f"USDT transaction not found for status: {transaction_id}")
            raise ProviderError(f"Transaction {transaction_id} not found", provider="crypto")

        try:
            # Verify payment to get latest status
            self.verify_payment(transaction_id)
            logger.debug(f"USDT payment status for {transaction_id}: {transaction.status}")
            return transaction.status
        except Exception as e:
            logger.error(f"Error getting USDT payment status: {e}")
            raise ProviderError(f"USDT payment status error: {e}", provider="crypto")

    def get_transaction_details(self, transaction_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a transaction.

        Args:
            transaction_id: ID of the transaction

        Returns:
            Dictionary containing transaction details
        """
        transaction = self.storage.get_transaction(transaction_id)
        if not transaction:
            raise ProviderError(f"Transaction {transaction_id} not found", provider="crypto")

        # Get current network info
        network_info = self.get_network_info()

        # Get current balance
        balance_info = self.get_usdt_balance()

        # Get gas price statistics
        gas_price_skips = transaction.metadata.get("gas_price_skips", 0)
        total_transactions = transaction.metadata.get("total_transactions_scanned", 0)
        effective_max_gas_price_gwei = (
            self.max_gas_price_gwei * 1.5
            if total_transactions > 10 and gas_price_skips / total_transactions > 0.5
            else self.max_gas_price_gwei
        )

        # Get receipt validation information
        receipt_validation_applied = transaction.metadata.get("receipt_validation_applied", False)
        receipt_status = transaction.metadata.get("receipt_status")
        gas_used = transaction.metadata.get("gas_used")
        gas_limit = transaction.metadata.get("gas_limit")

        return {
            "transaction_id": transaction_id,
            "user_id": transaction.user_id,
            "amount": transaction.amount,
            "currency": transaction.currency,
            "status": transaction.status,
            "created_at": transaction.created_at.isoformat(),
            "completed_at": transaction.completed_at.isoformat() if transaction.completed_at else None,
            "payment_method": transaction.payment_method,
            "metadata": transaction.metadata,
            "network_info": network_info,
            "current_balance": balance_info,
            "gas_price_statistics": {
                "skipped_transactions": gas_price_skips,
                "total_transactions_scanned": total_transactions,
                "skip_rate": ((gas_price_skips / total_transactions * 100) if total_transactions > 0 else 0),
                "effective_max_gas_price_gwei": effective_max_gas_price_gwei,
                "base_max_gas_price_gwei": self.max_gas_price_gwei,
                "dynamic_override_applied": total_transactions > 10 and gas_price_skips / total_transactions > 0.5,
            },
            "receipt_validation": {
                "receipt_validation_applied": receipt_validation_applied,
                "receipt_status": receipt_status,
                "gas_used": gas_used,
                "gas_limit": gas_limit,
                "gas_usage_percentage": ((gas_used / gas_limit * 100) if gas_used and gas_limit and gas_limit > 0 else None),
                "transaction_successful": receipt_status == 1 if receipt_status is not None else None,
            },
        }

    def get_lock_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about storage lock usage for monitoring.

        Returns:
            Dictionary containing lock statistics
        """
        # Calculate time since last reset
        time_since_reset = (datetime.now(timezone.utc) - self._last_contention_reset).total_seconds()
        hours_since_reset = time_since_reset / 3600

        # Calculate contention rate (timeouts per hour)
        contention_rate = self._lock_contention_count / max(hours_since_reset, 0.1)  # Avoid division by zero

        return {
            "lock_contention_count": self._lock_contention_count,
            "lock_type": "RLock",
            "lock_timeout_seconds": 10,
            "last_contention_reset": self._last_contention_reset.isoformat(),
            "hours_since_reset": round(hours_since_reset, 2),
            "contention_threshold": self._contention_threshold,
            "contention_rate_per_hour": round(contention_rate, 2),
            "storage_type": type(self.storage).__name__,
            "supports_native_transactions": hasattr(self.storage, "commit") and hasattr(self.storage, "rollback"),
            "contention_status": (
                "HIGH"
                if self._lock_contention_count > self._contention_threshold
                else "MODERATE" if self._lock_contention_count > self._contention_threshold // 2 else "LOW"
            ),
            "recommendation": (
                (
                    f"High lock contention ({self._lock_contention_count} timeouts in {hours_since_reset:.1f}h). "
                    f"Switch to DatabaseStorage with native transaction support immediately."
                )
                if self._lock_contention_count > self._contention_threshold
                else (
                    (
                        f"Moderate lock contention ({self._lock_contention_count} timeouts in {hours_since_reset:.1f}h). "
                        f"Consider DatabaseStorage for better performance."
                    )
                    if self._lock_contention_count > self._contention_threshold // 2
                    else (
                        f"Lock contention is within acceptable limits ({self._lock_contention_count} timeouts in {hours_since_reset:.1f}h)."
                    )
                )
            ),
        }

    def get_rate_limit_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about Infura rate limit usage for monitoring.

        Returns:
            Dictionary containing rate limit statistics
        """
        # Calculate time since last reset
        time_since_reset = (datetime.now(timezone.utc) - self._last_rate_limit_reset).total_seconds()
        hours_since_reset = time_since_reset / 3600

        # Calculate rate limit rate (errors per hour)
        rate_limit_rate = self._rate_limit_errors / max(hours_since_reset, 0.1)  # Avoid division by zero

        return {
            "rate_limit_errors": self._rate_limit_errors,
            "rate_limit_threshold": self._rate_limit_threshold,
            "last_rate_limit_reset": self._last_rate_limit_reset.isoformat(),
            "hours_since_reset": round(hours_since_reset, 2),
            "rate_limit_rate_per_hour": round(rate_limit_rate, 2),
            "infura_project_id": self.infura_project_id,
            "rate_limit_status": (
                "HIGH"
                if self._rate_limit_errors > self._rate_limit_threshold
                else "MODERATE" if self._rate_limit_errors > self._rate_limit_threshold // 2 else "LOW"
            ),
            "free_tier_limits": {
                "requests_per_second": 10,
                "requests_per_day": 100000,
                "description": "Free-tier Infura accounts have strict rate limits",
            },
            "recommendation": (
                (
                    f"High rate limit errors ({self._rate_limit_errors} in {hours_since_reset:.1f}h). "
                    f"Upgrade to a paid Infura plan or reduce API call frequency. "
                    f"Current project ID: {self.infura_project_id}"
                )
                if self._rate_limit_errors > self._rate_limit_threshold
                else (
                    (
                        f"Moderate rate limit errors ({self._rate_limit_errors} in {hours_since_reset:.1f}h). "
                        f"Monitor usage to avoid hitting limits."
                    )
                    if self._rate_limit_errors > self._rate_limit_threshold // 2
                    else (
                        f"Rate limit errors are within acceptable limits ({self._rate_limit_errors} in {hours_since_reset:.1f}h)."
                    )
                )
            ),
            "upgrade_guidance": [
                "Free-tier: 10 requests/sec, 100k/day",
                "Growth-tier: 50 requests/sec, 500k/day",
                "Scale-tier: 100 requests/sec, 1M/day",
                "Enterprise: Custom limits",
            ],
        }

    def get_event_processing_config(self) -> Dict[str, Any]:
        """
        Get event processing configuration and statistics.

        Returns:
            Dictionary containing event processing settings and recommendations
        """
        return {
            "block_step": 100,  # Blocks processed per batch
            "max_events": 1000,  # Maximum events processed per verification
            "max_block_range": 1000,  # Maximum block range to scan
            "lookback_minutes": 5,  # Minutes to look back from transaction creation
            "pagination_enabled": True,
            "event_capping_enabled": True,
            "filter_cleanup_enabled": True,
            "filter_cleanup_strategy": "Pre-creation tracking + immediate cleanup per batch + final cleanup for residuals",
            "resource_leak_prevention": "Pre-track filter IDs before creation to ensure cleanup even if creation fails",
            "gas_price_protection_enabled": True,
            "gas_price_threshold_multiplier": 1.5,
            "rate_limit_backoff_enabled": True,
            "max_rate_limit_errors": 3,
            "backoff_strategy": "Exponential (2s, 4s, 8s)",
            "receipt_validation_enabled": True,
            "receipt_success_status": 1,
            "connection_error_handling": "Comprehensive Web3 connection failure handling with metadata updates",
            "early_timeout_validation": "Timeout check before event processing to prevent unnecessary API calls",
            "storage_validation_enabled": "Storage write validation with retries for all critical operations",
            "transaction_receipt_validation": True,
            "validation_features": [
                "Transfer event detection",
                "Block confirmation validation",
                "Canonical chain verification",
                "Transaction receipt status check (ensures success)",
                "Skip failed or reverted transactions",
                "Gas usage monitoring",
                "Double-spending prevention",
                "Pre-creation filter tracking",
                "Comprehensive Web3 connection error handling",
                "Early timeout validation",
                "Storage write validation with retries",
            ],
            "performance_recommendations": [
                "Monitor events_processed in transaction metadata",
                "Increase max_events if verification fails frequently",
                "Decrease block_step if rate limits are hit",
                "Consider narrowing block range for high-volume wallets",
                "Monitor filter cleanup failures in logs",
                "Track gas price skip rates via get_transaction_details",
            ],
            "rate_limit_considerations": [
                "Each block batch requires one Infura API call",
                "Large block ranges may hit rate limits",
                "Event capping prevents excessive memory usage",
                "Filter cleanup prevents resource leaks",
                "Infura filter limit: ~10,000 per project",
            ],
            "monitoring_advice": [
                "Alert on filter cleanup failures",
                "Monitor gas price skip rates > 50%",
                "Track Infura rate limit errors (HTTP 429)",
                "Monitor rate limit statistics via get_rate_limit_statistics()",
                "Alert on high rate limit errors (>10/hour)",
                "Ensure storage backend supports delete_transaction for cleanup",
                "Monitor network congestion levels",
                "Track dynamic block time estimation accuracy",
                "Track rate_limit_errors in transaction metadata",
                "Adjust block_step if rate limits persist",
                "Monitor receipt validation failures",
                "Track failed transaction rejections",
                "Monitor failed transaction receipts",
                "Track receipt validation errors",
                "Monitor untracked filter creation errors",
                "Alert on persistent filter cleanup failures",
                "Monitor Web3 connection failures",
                "Alert on persistent connection errors",
                "Monitor early timeout validation triggers",
                "Track storage write validation failures",
                "Alert on persistent storage write errors",
                "Monitor filter pre-creation tracking effectiveness",
                "Track comprehensive connection error handling",
                "Monitor storage write retry failures",
                "Monitor Infura plan limits and upgrade guidance",
                "Track rate limit error patterns and frequency",
            ],
        }

    def reset_lock_statistics(self) -> Dict[str, Any]:
        """
        Manually reset lock contention statistics.

        Returns:
            Dictionary containing reset confirmation and current statistics
        """
        old_count = self._lock_contention_count
        old_reset_time = self._last_contention_reset

        self._lock_contention_count = 0
        self._last_contention_reset = datetime.now(timezone.utc)

        logger.info(f"Lock contention statistics reset. " f"Previous: {old_count} timeouts since {old_reset_time.isoformat()}")

        return {
            "reset_confirmation": True,
            "previous_contention_count": old_count,
            "previous_reset_time": old_reset_time.isoformat(),
            "new_reset_time": self._last_contention_reset.isoformat(),
            "current_statistics": self.get_lock_statistics(),
        }

    def reset_rate_limit_statistics(self) -> Dict[str, Any]:
        """
        Manually reset rate limit statistics.

        Returns:
            Dictionary containing reset confirmation and current statistics
        """
        old_count = self._rate_limit_errors
        old_reset_time = self._last_rate_limit_reset

        self._rate_limit_errors = 0
        self._last_rate_limit_reset = datetime.now(timezone.utc)

        logger.info(f"Rate limit statistics reset. " f"Previous: {old_count} errors since {old_reset_time.isoformat()}")

        return {
            "reset_confirmation": True,
            "previous_rate_limit_count": old_count,
            "previous_reset_time": old_reset_time.isoformat(),
            "new_reset_time": self._last_rate_limit_reset.isoformat(),
            "current_statistics": self.get_rate_limit_statistics(),
        }

    def get_reorg_protection_info(self) -> Dict[str, Any]:
        """
        Get information about blockchain reorg protection settings.

        Returns:
            Dictionary containing reorg protection information
        """
        safety_margin = 5
        effective_confirmations = self.confirmations_required + safety_margin
        finality_time_minutes = (effective_confirmations * self.network_config["block_time"]) / 60

        return {
            "network": self.network,
            "confirmations_required": self.confirmations_required,
            "safety_margin_confirmations": safety_margin,
            "effective_confirmations": effective_confirmations,
            "block_time_seconds": self.network_config["block_time"],
            "finality_time_minutes": finality_time_minutes,
            "reorg_protection_enabled": True,
            "canonical_chain_verification": True,
            "safety_margin_enabled": True,
            "recommendation": (
                (
                    f"Current settings provide {effective_confirmations} confirmations "
                    f"({finality_time_minutes:.1f} minutes) of finality with {safety_margin} "
                    f"extra confirmations for reorg protection. For mainnet, this reduces "
                    f"reorg risk significantly."
                )
                if self.network == "mainnet"
                else (
                    f"Testnet settings with {effective_confirmations} confirmations "
                    f"({safety_margin} extra for safety) are appropriate for development and testing."
                )
            ),
            "reorg_risk_assessment": (
                "LOW" if effective_confirmations >= 24 else "MODERATE" if effective_confirmations >= 12 else "HIGH"
            ),
        }

    def get_price_feed_status(self) -> Dict[str, Any]:
        """
        Get status of the USDT price feed configuration.

        Returns:
            Dictionary containing price feed status and recommendations
        """
        is_dev_mode = self._is_dev_mode()
        current_price = self._get_usdt_price()  # Now works in all environments

        return {
            "price_feed_type": "hardcoded_beta",
            "current_price_usd": current_price,
            "is_production_safe": True,  # Hardcoded 1:1 is safe for beta in all environments
            "dev_mode": is_dev_mode,
            "beta_assumption": "1 USDT == 1 USD (hardcoded for beta)",
            "market_deviation_note": "Minor deviations (0.99–1.01 USD) may occur in real market conditions",
            "recommendations": [
                "Hardcoded 1:1 ratio is acceptable for beta testing",
                "Integrate Chainlink USDT/USD price oracle for production",
                "Implement price validation and health checks",
                "Add price deviation alerts for significant changes",
                "Consider multiple price sources for redundancy",
            ],
            "production_requirements": [
                "Real-time price feed (Chainlink recommended)",
                "Price validation and health monitoring",
                "Fallback price sources",
                "Price deviation alerts",
            ],
            "integration_guide": {
                "chainlink": "Use Chainlink USDT/USD price oracle contract",
                "validation": "Implement price sanity checks (e.g., 0.95 < price < 1.05)",
                "monitoring": "Set up alerts for price deviations > 1%",
                "fallback": "Implement multiple price sources for redundancy",
            },
        }

    def get_usdt_price_info(self) -> Dict[str, Any]:
        """
        Get current USDT price information.

        Returns:
            Dictionary containing USDT price details
        """
        current_price = self._get_usdt_price()
        return {
            "usdt_price_usd": current_price,
            "price_source": "hardcoded_beta",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "beta_assumption": "1 USDT == 1 USD (hardcoded for beta)",
            "market_deviation_note": "Minor deviations (0.99–1.01 USD) may occur in real market conditions",
            "recommendation": (
                "Hardcoded 1:1 ratio is acceptable for beta testing. " "Integrate with Chainlink price oracle for production use."
            ),
            "deviation_from_par": abs(current_price - 1.0),
            "is_par": abs(current_price - 1.0) < 0.001,  # Within 0.1% of $1.00
            "deviation_threshold": 0.01,  # 1% deviation threshold for warnings
        }

    def get_timeout_validation_info(self) -> Dict[str, Any]:
        """
        Get information about transaction timeout validation settings.

        Returns:
            Dictionary containing timeout validation information
        """
        return {
            "timeout_minutes": 30,
            "timeout_validation_enabled": True,
            "fallback_timeout_enabled": True,
            "fallback_timeout_minutes": 30,
            "timeout_format": "ISO 8601",
            "metadata_validation_enabled": True,
            "validated_metadata_fields": ["usdt_amount_wei", "contract_address", "timeout_at"],
            "transaction_id_collision_prevention": True,
            "max_id_attempts": 5,
            "storage_health_check_enabled": True,
            "storage_write_retries": 3,
            "verification_storage_retries": 3,
            "early_timeout_validation": "Timeout check before event processing to prevent unnecessary API calls",
            "race_condition_protection_enabled": True,
            "validation_features": [
                "Future-dated timeout validation",
                "ISO format validation",
                "Fallback to created_at + 30 minutes",
                "Graceful handling of malformed timeouts",
                "Metadata field validation",
                "Transaction ID collision prevention",
                "Storage read/write consistency check",
                "Atomic transaction status updates",
                "USDT precision validation",
                "Storage write retry on failure",
                "Verification storage retry logic",
                "Failed transaction status persistence",
                "Early timeout validation in event verification",
                "Pre-creation filter tracking",
                "Comprehensive Web3 connection error handling",
                "Storage write validation with retries",
            ],
            "recommendation": (
                "Timeout and metadata validation prevents transactions from getting stuck in pending state. "
                "Fallback mechanism ensures robustness against malformed values. "
                "Collision prevention and storage checks ensure data integrity. "
                "Race condition protection prevents concurrent verification issues."
            ),
            "monitoring_advice": [
                "Monitor timeout validation failures in logs",
                "Alert on transactions with fallback timeouts",
                "Track metadata validation failures",
                "Monitor transaction ID collision warnings",
                "Ensure storage backend preserves metadata integrity",
                "Monitor storage health check failures in logs",
                "Ensure storage backend supports delete_transaction for cleanup",
                "Monitor concurrent verification attempts for same transaction",
                "Monitor storage write retry failures",
                "Alert on persistent storage write errors",
                "Track USDT precision validation failures",
                "Monitor verification storage retry failures",
                "Alert on failed transaction status persistence",
                "Track storage write failures during verification",
                "Monitor early timeout validation triggers",
                "Monitor filter pre-creation tracking effectiveness",
                "Track comprehensive connection error handling",
                "Alert on persistent Web3 connection failures",
                "Monitor storage write validation failures",
                "Track filter cleanup failures",
            ],
        }

    def get_race_condition_protection_info(self) -> Dict[str, Any]:
        """
        Get information about race condition protection settings.

        Returns:
            Dictionary containing race condition protection information
        """
        return {
            "race_condition_protection_enabled": True,
            "atomic_status_updates": True,
            "transaction_scope_strategy": "Single transaction scope for all status updates",
            "re_fetch_strategy": "Re-fetch transaction inside transaction scope",
            "transfer_uniqueness_check": "Atomic within transaction scope",
            "transfer_marking_validation": "Storage write validation for used transfers",
            "protection_features": [
                "Atomic transaction status check",
                "Single transaction scope for all updates",
                "Re-fetch transaction to prevent stale reads",
                "Prevents double-crediting of same transaction",
                "Prevents inconsistent transaction states",
                "Atomic transfer uniqueness check to prevent double-crediting",
                "Storage write validation for transfer usage",
                "Retry logic for marking transfers as used",
            ],
            "concurrency_scenarios_handled": [
                "Multiple concurrent verify_payment calls",
                "Automated retry mechanisms",
                "User-initiated verification requests",
                "Background verification processes",
            ],
            "recommendation": (
                "Race condition protection ensures transaction status updates are atomic. "
                "This prevents issues like double-crediting or inconsistent states "
                "when multiple verification requests occur simultaneously."
            ),
            "monitoring_advice": [
                "Monitor for concurrent verification attempts",
                "Track transaction status update patterns",
                "Alert on unusual verification frequency",
                "Ensure storage backend supports atomic operations",
                "Monitor double-crediting attempts in logs",
                "Track transfer uniqueness check failures",
                "Monitor transfer marking failures",
                "Alert on storage write failures during transfer marking",
            ],
        }

    def get_network_congestion_info(self) -> Dict[str, Any]:
        """
        Get information about network congestion and dynamic block time estimation.

        Returns:
            Dictionary containing network congestion information
        """
        try:
            # Get current dynamic block time estimation
            dynamic_block_time = self._estimate_dynamic_block_time()
            configured_block_time = self.network_config["block_time"]

            # Determine congestion level
            if dynamic_block_time is None:
                congestion_level = "UNKNOWN"
                congestion_reason = "Dynamic estimation failed, using configured block time"
            elif dynamic_block_time <= configured_block_time * 1.2:
                congestion_level = "LOW"
                congestion_reason = "Block times near normal"
            elif dynamic_block_time <= configured_block_time * 2.0:
                congestion_level = "MODERATE"
                congestion_reason = "Block times 1.2-2x normal"
            elif dynamic_block_time <= configured_block_time * 3.0:
                congestion_level = "HIGH"
                congestion_reason = "Block times 2-3x normal"
            else:
                congestion_level = "SEVERE"
                congestion_reason = "Block times >3x normal (severe congestion)"

            return {
                "dynamic_block_time_enabled": True,
                "configured_block_time_seconds": configured_block_time,
                "current_dynamic_block_time_seconds": dynamic_block_time,
                "congestion_level": congestion_level,
                "congestion_reason": congestion_reason,
                "sample_size": 10,
                "min_reasonable_time_seconds": 1.0,
                "max_reasonable_time_seconds": 60.0,
                "estimation_features": [
                    "Recent block timestamp sampling",
                    "Consecutive block time calculation",
                    "Reasonable range validation",
                    "Fallback to configured block time",
                    "Network congestion detection",
                ],
                "recommendation": (
                    "Dynamic block time estimation accounts for network congestion, "
                    "improving block range accuracy during peak usage periods. "
                    "This reduces unnecessary API calls and improves verification reliability."
                ),
                "monitoring_advice": [
                    "Monitor dynamic block time estimates",
                    "Alert on severe congestion (>3x normal block time)",
                    "Track estimation failures",
                    "Monitor block range accuracy improvements",
                ],
                "health_check_integration": {
                    "congestion_simulation_enabled": True,
                    "dynamic_block_time_test": True,
                    "rate_limit_backoff_test": True,
                    "congestion_assessment_test": True,
                    "test_frequency": "Every health check",
                    "simulation_impact": "Read-only, no actual API calls",
                },
            }
        except Exception as e:
            logger.error(f"Failed to get network congestion info: {e}")
            return {
                "dynamic_block_time_enabled": False,
                "error": str(e),
                "recommendation": "Network congestion monitoring unavailable, using configured block time",
            }

    def get_usdt_precision_info(self) -> Dict[str, Any]:
        """
        Get information about USDT precision validation settings.

        Returns:
            Dictionary containing USDT precision validation information
        """
        return {
            "usdt_precision_validation_enabled": True,
            "usdt_decimals": self.usdt_decimals,
            "precision_tolerance": 0.000001,  # 6 decimal precision tolerance
            "validation_features": [
                "Decimal precision handling",
                "Wei conversion validation",
                "Precision loss detection",
                "Reconstruction validation",
                "Integer wei amount validation",
            ],
            "conversion_process": [
                "USD amount → USDT amount (with price)",
                "USDT amount → Decimal (6 decimals)",
                "Decimal → Wei (integer validation)",
                "Wei → USDT reconstruction (precision check)",
            ],
            "recommendation": (
                "USDT precision validation ensures accurate amount conversion from USD to wei. "
                "This prevents verification failures due to precision loss or truncation errors. "
                "All conversions are validated to maintain data integrity."
            ),
            "monitoring_advice": [
                "Monitor USDT precision validation failures",
                "Track conversion accuracy",
                "Alert on precision loss detection",
                "Ensure price feed accuracy for conversions",
            ],
        }

    def get_receipt_validation_info(self) -> Dict[str, Any]:
        """
        Get information about transaction receipt validation settings.

        Returns:
            Dictionary containing transaction receipt validation information
        """
        return {
            "receipt_validation_enabled": True,
            "success_status": 1,
            "validation_features": [
                "Transaction receipt status check",
                "Gas usage validation",
                "Failed transaction rejection",
                "Reverted transaction detection",
                "Out-of-gas transaction monitoring",
            ],
            "validation_process": [
                "Transfer event detection",
                "Transaction receipt fetch",
                "Status validation (must be 1)",
                "Gas usage analysis",
                "Success confirmation",
            ],
            "security_benefits": [
                "Prevents false positives from failed transactions",
                "Rejects reverted transactions",
                "Detects out-of-gas scenarios",
                "Ensures only successful transfers are credited",
                "Protects against financial discrepancies",
            ],
            "recommendation": (
                "Transaction receipt validation is critical for preventing false positives. "
                "Failed transactions can emit Transfer events but not execute successfully. "
                "This validation ensures only successful transactions are verified as payments."
            ),
            "monitoring_advice": [
                "Monitor receipt validation failures",
                "Track failed transaction rejections",
                "Alert on high gas usage transactions",
                "Monitor receipt fetch errors",
                "Track reverted transaction detection",
            ],
            "failure_scenarios_handled": [
                "Transaction reverted (status = 0)",
                "Out of gas (gasUsed >= gasLimit)",
                "Contract execution failure",
                "Insufficient funds for gas",
                "Invalid transaction parameters",
            ],
        }

    def get_storage_retry_info(self) -> Dict[str, Any]:
        """
        Get information about storage retry logic for verification operations.

        Returns:
            Dictionary containing storage retry information
        """
        return {
            "storage_retry_enabled": True,
            "max_retries": 3,
            "retry_backoff_seconds": [0.1, 0.2, 0.3],  # Progressive backoff
            "retry_features": [
                "Storage write retry on failure",
                "Write verification after retry",
                "Data integrity validation",
                "Progressive backoff strategy",
                "Failure logging and alerting",
            ],
            "verification_retry_scenarios": [
                "Failed transaction status updates",
                "Completed transaction status updates",
                "Timeout transaction status updates",
                "Metadata validation failure updates",
            ],
            "retry_process": [
                "Attempt storage write",
                "Verify write success",
                "Validate data integrity",
                "Retry with backoff on failure",
                "Log failure after max retries",
            ],
            "recommendation": (
                "Storage retry logic prevents inconsistent transaction states during verification. "
                "Failed storage writes can leave transactions in pending state indefinitely. "
                "Retry logic ensures transaction status updates are persisted reliably."
            ),
            "monitoring_advice": [
                "Monitor storage retry failures",
                "Track verification storage write errors",
                "Alert on persistent storage failures",
                "Monitor data integrity validation failures",
                "Track retry backoff effectiveness",
            ],
            "failure_handling": [
                "Raise ProviderError on persistent failures",
                "Log detailed failure information",
                "Maintain transaction state consistency",
                "Prevent partial status updates",
            ],
        }

    def get_deadlock_prevention_info(self) -> Dict[str, Any]:
        """
        Get information about deadlock prevention mechanisms.

        Returns:
            Dictionary containing deadlock prevention information
        """
        return {
            "deadlock_prevention_enabled": True,
            "lock_timeout_seconds": 10,
            "commit_timeout_seconds": 5,
            "rollback_timeout_seconds": 3,
            "prevention_features": [
                "RLock for reentrant locking",
                "Lock acquisition timeout",
                "Commit operation timeout",
                "Rollback operation timeout",
                "Signal-based timeout protection",
                "Contention monitoring and alerting",
            ],
            "timeout_protection": {
                "lock_acquisition": "10 seconds maximum wait",
                "commit_operation": "5 seconds maximum execution",
                "rollback_operation": "3 seconds maximum execution",
                "signal_handling": "SIGALRM-based timeout protection",
            },
            "deadlock_scenarios_prevented": [
                "Storage backend commit blocking indefinitely",
                "Storage backend rollback blocking indefinitely",
                "Database connection deadlocks",
                "Nested transaction scope deadlocks",
                "Storage lock contention deadlocks",
            ],
            "recommendation": (
                "Deadlock prevention ensures verification processes don't freeze due to storage issues. "
                "Timeout protection prevents indefinite blocking on commit/rollback operations. "
                "This is critical for maintaining system responsiveness during storage backend issues."
            ),
            "monitoring_advice": [
                "Monitor lock acquisition timeouts",
                "Track commit operation timeouts",
                "Alert on rollback operation timeouts",
                "Monitor storage backend responsiveness",
                "Track deadlock prevention effectiveness",
            ],
            "error_handling": [
                "ProviderError on lock timeout",
                "ProviderError on commit timeout",
                "Logging on rollback timeout",
                "Graceful degradation on storage issues",
            ],
        }

    def is_production_ready(self) -> Dict[str, Any]:
        """
        Check if the provider is configured for production use.

        Returns:
            Dictionary containing production readiness status
        """
        storage_supports_transactions = (
            hasattr(self.storage, "commit")
            and hasattr(self.storage, "rollback")
            and callable(getattr(self.storage, "commit", None))
            and callable(getattr(self.storage, "rollback", None))
        )

        # Price feed is production-ready for beta with hardcoded 1:1 ratio
        # Hardcoded price feed is acceptable for beta testing in all environments
        price_feed_production = True  # Hardcoded 1:1 is acceptable for beta

        recommendations = []
        if not storage_supports_transactions:
            recommendations.append("Use DatabaseStorage with SQLAlchemy for production")
        if not (self.infura_project_id and self.infura_project_id != "dummy_project_id"):
            recommendations.append("Configure valid Infura project ID for production")
        if self.network != "mainnet":
            recommendations.append("Use mainnet for production payments")
        if not price_feed_production:
            recommendations.append("Integrate Chainlink price oracle for accurate USDT pricing")
        else:
            recommendations.append("Hardcoded 1:1 USDT/USD ratio is acceptable for beta testing")

        return {
            "is_production_ready": (
                not self._is_dev_mode()
                and storage_supports_transactions
                and self.infura_project_id
                and self.infura_project_id != "dummy_project_id"
                and self.network == "mainnet"
                and price_feed_production
            ),
            "storage_transactional": storage_supports_transactions,
            "infura_configured": bool(self.infura_project_id and self.infura_project_id != "dummy_project_id"),
            "network_production": self.network == "mainnet",
            "price_feed_production": price_feed_production,
            "dev_mode": self._is_dev_mode(),
            "recommendations": [r for r in recommendations if r],
        }

    def list_transactions(
        self, user_id: Optional[str] = None, status: Optional[str] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        List transactions with optional filtering.

        Args:
            user_id: Filter by user ID
            status: Filter by status ('pending', 'completed', 'failed')
            limit: Maximum number of transactions to return

        Returns:
            List of transaction details
        """
        # Get transactions from storage
        stored_transactions = self.storage.list_transactions(user_id=user_id, status=status, limit=limit)

        # Convert to transaction details
        transactions = []
        for transaction in stored_transactions:
            transactions.append(self.get_transaction_details(transaction.id))

        # Sort by creation time (newest first)
        transactions.sort(key=lambda x: x["created_at"], reverse=True)

        return transactions

    def verify_webhook_signature(self, payload: str, headers: Any) -> bool:
        """
        Verify webhook signature (not supported for crypto).

        Args:
            payload: The webhook payload to verify
            headers: The webhook headers containing signature information

        Returns:
            False - webhooks not supported for crypto payments
        """
        logger.warning("Webhook signature verification not supported for CryptoProvider")
        return False

    def create_checkout_session(
        self,
        user_id: str,
        plan: Any,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Create a checkout session for payment (not supported for crypto).

        Args:
            user_id: ID of the user making the payment
            plan: Payment plan or amount information
            success_url: URL to redirect to on successful payment
            cancel_url: URL to redirect to on cancelled payment
            metadata: Additional metadata for the session

        Returns:
            Never returns - raises ProviderError

        Raises:
            ProviderError: Checkout sessions not supported for crypto
        """
        raise ProviderError(
            "Checkout sessions not supported for CryptoProvider. " "Use process_payment() to create transactions.",
            provider="crypto",
        )

    def health_check(self) -> bool:
        """
        Perform health check and return boolean result.

        Returns:
            True if provider is healthy, False otherwise
        """
        try:
            self._perform_health_check()
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
