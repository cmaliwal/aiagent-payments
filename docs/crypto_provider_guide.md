# USDT ERC-20 Payment Provider Guide

## Overview

The Crypto Provider enables USDT (Tether) ERC-20 token payments on Ethereum networks using web3.py and Infura. This provider offers production-ready cryptocurrency payment processing with comprehensive blockchain verification and security features.

## Supported Networks

**Currently Supported:**
- **Ethereum Mainnet** - Production network for real USDT payments
- **Sepolia Testnet** - Test network for development and testing

**Not Supported:**
- Goerli testnet (deprecated and will be shut down)
- Other Ethereum-compatible networks (can be added via custom configuration)

## API Requirements

### Required API Keys

1. **Infura Project ID** (`INFURA_PROJECT_ID`)
   - Used for Ethereum network connectivity
   - Get your project ID at: https://infura.io/
   - Free tier available with generous limits

2. **Wallet Address** (`WALLET_ADDRESS`)
   - Your Ethereum wallet address to receive USDT payments
   - Must be a valid Ethereum address (checksummed)
   - Used for payment verification and refunds

### Environment Setup

```bash
export INFURA_PROJECT_ID="your_infura_project_id"
export WALLET_ADDRESS="0xYourWalletAddress"
```

## Important Features

### 1. Multi-Network Support

**Production vs Testing:**
- Use `mainnet` for real USDT payments
- Use `sepolia` for development and testing
- Automatic network-specific configuration

```python
# Production setup
provider = CryptoProvider(
    wallet_address="0xYourWalletAddress",
    infura_project_id="your_infura_project_id",
    network="mainnet"
)

# Testing setup
provider = CryptoProvider(
    wallet_address="0xYourTestWalletAddress",
    infura_project_id="your_infura_project_id",
    network="sepolia"
)
```

### 2. On-Chain Payment Verification

**Comprehensive Verification:**
- Monitors USDT transfer events on blockchain
- Configurable confirmation requirements
- Prevents double-spending and replay attacks
- Real-time transaction status updates

```python
# Process payment
transaction = provider.process_payment(
    user_id="user123",
    amount=25.0,
    currency="USD",
    metadata={"sender_address": "0xYourSenderAddress", "description": "AI service payment"}
)

# Verify payment with confirmations
if provider.verify_payment(transaction.id):
    print("Payment confirmed on blockchain!")
else:
    print("Payment pending confirmation...")
```

### 3. Security Features

**Built-in Security:**
- Address validation and checksum verification
- Gas price limits to prevent overpayment
- Transaction confirmation requirements
- Rate limiting and retry mechanisms
- Comprehensive error handling

## Best Practices

### 1. Payment Processing

```python
from aiagent_payments.providers.crypto import CryptoProvider

# Initialize provider
provider = CryptoProvider(
    wallet_address="0xYourWalletAddress",
    infura_project_id="your_infura_project_id",
    network="mainnet"
)

# Process USDT payment
transaction = provider.process_payment(
    user_id="user123",
    amount=50.0,
    currency="USD",
    metadata={"sender_address": "0xYourSenderAddress", "description": "AI service payment"}
)

print(f"Payment created: {transaction.id}")
print(f"USDT amount: {transaction.metadata.get('usdt_amount')} USDT")
print(f"Wallet address: {transaction.metadata.get('wallet_address')}")
```

### 2. Payment Verification

```python
# Monitor for payment confirmation
max_attempts = 20
for attempt in range(max_attempts):
    if provider.verify_payment(transaction.id):
        print("Payment confirmed!")
        break
    time.sleep(30)  # Wait 30 seconds between checks
    print(f"Waiting for confirmation... (attempt {attempt + 1})")
else:
    print("Payment not confirmed within expected time")
```

### 3. Error Handling

```python
try:
    transaction = provider.process_payment(user_id, amount, "USD")
except ProviderError as e:
    if "Invalid wallet address" in str(e):
        print("Check your wallet address format")
    elif "Infura connection failed" in str(e):
        print("Check your Infura project ID and network connectivity")
    else:
        print(f"Provider error: {e}")
except PaymentFailed as e:
    print(f"Payment failed: {e}")
```

### 4. Production Considerations

**Wallet Management:**
- Use hardware wallets for large amounts
- Implement proper key management
- Set up secure wallet infrastructure
- Monitor wallet balances regularly

**Network Monitoring:**
- Monitor gas fees and network congestion
- Set up alerts for failed transactions
- Track confirmation times
- Monitor Infura rate limits

**Security:**
- Never expose private keys
- Use environment variables for sensitive data
- Implement proper access controls
- Regular security audits

## Example Usage

### Basic Payment Flow

```python
from aiagent_payments.providers.crypto import CryptoProvider
import time

# Initialize provider
provider = CryptoProvider(
    wallet_address="0xYourWalletAddress",
    infura_project_id="your_infura_project_id",
    network="mainnet"
)

# Create payment
transaction = provider.process_payment(
    user_id="user123",
    amount=100.0,
    currency="USD",
    metadata={"sender_address": "0xYourSenderAddress", "description": "AI service payment"}
)

print(f"Payment ID: {transaction.id}")
print(f"USDT Amount: {transaction.metadata.get('usdt_amount')} USDT")
print(f"Wallet Address: {transaction.metadata.get('wallet_address')}")

# Monitor for confirmation
while not provider.verify_payment(transaction.id):
    time.sleep(30)
    print("Waiting for confirmation...")

print("Payment confirmed!")
```

### Refund Process

```python
# Only refund confirmed payments
if provider.verify_payment(transaction.id):
    refund_info = provider.refund_payment(transaction.id, amount=100.0)
    
    print("Refund Instructions:")
    print(refund_info['instructions'])
    print(f"Transaction Hash: {refund_info['transaction_hash']}")
    print(f"Wallet Address: {refund_info['wallet_address']}")
    print(f"Amount: {refund_info['amount']} USD")
    print(f"USDT Amount: {refund_info['usdt_amount']} USDT")
    
    # Manual steps required:
    # 1. Use your wallet to send refund
    # 2. Track the refund transaction
    # 3. Update your records
else:
    print("Cannot refund - payment not confirmed")
```

### Health Monitoring

```python
# Check provider health
health_status = provider.check_health()
print(f"Provider healthy: {health_status.is_healthy}")
print(f"Network: {health_status.details.get('network')}")
print(f"Block height: {health_status.details.get('block_height')}")

# Get provider capabilities
capabilities = provider.get_capabilities()
print(f"Supports refunds: {capabilities.supports_refunds}")
print(f"Supports partial refunds: {capabilities.supports_partial_refunds}")
print(f"Network info: {capabilities.network_info}")
```

## Sender Address Requirement for USDT ERC-20

When processing USDT ERC-20 payments, you must provide the sender's Ethereum address in the `metadata` as `sender_address`. The payment will only be credited if the funds are sent from this address.

Example:

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

## Troubleshooting

### Common Issues

**1. "Invalid wallet address" error**
- Solution: Ensure wallet address is valid Ethereum address with checksum
- Use `Web3.to_checksum_address()` to validate

**2. "Infura connection failed" error**
- Solution: Check your Infura project ID and network connectivity
- Verify project is active and has sufficient credits

**3. "Payment not confirmed" error**
- Solution: Wait for blockchain confirmations (typically 1-6 blocks)
- Check network congestion and gas fees

**4. "Gas price too high" error**
- Solution: Adjust `max_gas_price_gwei` parameter or wait for lower gas prices
- Monitor Ethereum network conditions

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# This will show detailed web3 calls and responses
provider = CryptoProvider(
    wallet_address="0xYourWalletAddress",
    infura_project_id="your_infura_project_id",
    network="sepolia"  # Use testnet for debugging
)
```

## Network Configuration

### Mainnet Configuration
- **Network**: Ethereum Mainnet
- **Chain ID**: 1
- **Block Time**: ~12 seconds
- **Confirmations Required**: 12 blocks
- **Max Gas Price**: 100 gwei
- **USDT Contract**: `0xdAC17F958D2ee523a2206206994597C13D831ec7`

### Sepolia Testnet Configuration
- **Network**: Sepolia Testnet
- **Chain ID**: 11155111
- **Block Time**: ~12 seconds
- **Confirmations Required**: 6 blocks
- **Max Gas Price**: 50 gwei
- **USDT Contract**: `0x7169D38820dfd117C3FA1f22a697dBA58d90BA06`

## Migration Guide

### From Old Crypto Provider

If migrating from the old BlockCypher/CoinGecko implementation:

1. **Update Dependencies**: Install `web3` instead of `blockcypher`, `coingecko`
2. **Update API Keys**: Replace BlockCypher/CoinGecko keys with Infura project ID
3. **Update Configuration**: Use new provider initialization parameters
4. **Update Payment Flow**: USDT payments work differently than BTC/ETH
5. **Test Thoroughly**: Verify all payment flows work correctly

### From Other Crypto Providers

If migrating from other crypto providers:

1. **Set up Infura**: Create account and get project ID
2. **Configure Wallet**: Ensure wallet address is valid and has ETH for gas
3. **Update Code**: Use new provider interface
4. **Test on Sepolia**: Test thoroughly on testnet before mainnet
5. **Monitor Transactions**: Set up proper monitoring and alerts

## Support

For issues with the USDT crypto provider:

1. Check this guide for common solutions
2. Review the error messages and logs
3. Verify your Infura project ID and wallet address
4. Test with the provided examples
5. Check network status and gas prices

Remember: The USDT crypto provider is designed for production use with comprehensive security features. For testing, always use the Sepolia testnet first. 