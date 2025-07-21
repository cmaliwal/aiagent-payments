# USDT ERC-20 Payments Guide

A comprehensive guide to integrating USDT (Tether) ERC-20 token payments with AIAgent Payments using web3.py and Infura.

## 🎯 Overview

USDT ERC-20 payments offer secure, fast, and cost-effective cryptocurrency transactions on the Ethereum network. AIAgent Payments supports USDT payments on both Ethereum mainnet and Sepolia testnet with comprehensive blockchain verification and security features.

## 🚀 Quick Start

### Basic Setup

```python
from aiagent_payments.providers.crypto import CryptoProvider

# Initialize USDT provider
provider = CryptoProvider(
    wallet_address="0xYourWalletAddress",
    infura_project_id="your_infura_project_id",
    network="mainnet"  # or "sepolia" for testing
)

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
        "description": "AI Agent Consultation"
    }
)
```

# Process a USDT payment
transaction = provider.process_payment(
    user_id="user123",
    amount=50.0,  # $50.00 USD
    currency="USD",
    metadata={"description": "AI Agent Consultation"}
)

print(f"Payment ID: {transaction.id}")
print(f"USDT Amount: {transaction.metadata.get('usdt_amount')} USDT")
print(f"Wallet Address: {transaction.metadata.get('wallet_address')}")
```

### Environment Configuration

```bash
# Required environment variables
export INFURA_PROJECT_ID="your_infura_project_id"
export WALLET_ADDRESS="0xYourWalletAddress"

# Optional: Network configuration
export CRYPTO_NETWORK="mainnet"  # or "sepolia"
export CRYPTO_CONFIRMATIONS="12"  # mainnet default
export CRYPTO_MAX_GAS_PRICE="100"  # gwei
```

## 💰 Supported Networks

### Ethereum Mainnet

```python
# Production USDT payments
provider = CryptoProvider(
    wallet_address="0xYourWalletAddress",
    infura_project_id="your_infura_project_id",
    network="mainnet",
    confirmations_required=12,
    max_gas_price_gwei=100
)

# Process mainnet payment
transaction = provider.process_payment(
    user_id="user123",
    amount=100.0,  # $100.00
    currency="USD",
    metadata={"description": "AI Agent Service"}
)

print(f"Payment ID: {transaction.id}")
print(f"USDT Amount: {transaction.metadata.get('usdt_amount')} USDT")
print(f"Network: {provider.get_network_info()['name']}")
```

### Sepolia Testnet

```python
# Testing USDT payments
provider = CryptoProvider(
    wallet_address="0xYourTestWalletAddress",
    infura_project_id="your_infura_project_id",
    network="sepolia",
    confirmations_required=6,
    max_gas_price_gwei=50
)

# Process testnet payment
transaction = provider.process_payment(
    user_id="test_user",
    amount=10.0,  # $10.00
    currency="USD",
    metadata={"description": "Test payment"}
)
```

## 🔗 Payment Methods

### Direct USDT Payments

```python
# Accept direct USDT payments
transaction = provider.process_payment(
    user_id="user123",
    amount=25.0,
    currency="USD",
    metadata={"description": "AI Agent Service"}
)

print(f"USDT Address: {transaction.metadata.get('wallet_address')}")
print(f"Required Amount: {transaction.metadata.get('usdt_amount')} USDT")
print(f"Payment ID: {transaction.id}")
```

### Payment Verification

```python
# Monitor payment confirmation
def monitor_payment(transaction_id):
    max_attempts = 20
    for attempt in range(max_attempts):
        if provider.verify_payment(transaction_id):
            print(f"✅ Payment {transaction_id} confirmed!")
            return True
        time.sleep(30)  # Wait 30 seconds
        print(f"⏳ Waiting for confirmation... (attempt {attempt + 1})")
    
    print(f"❌ Payment {transaction_id} not confirmed within time limit")
    return False

# Use the monitoring function
if monitor_payment(transaction.id):
    # Grant access to AI agent features
    grant_access(transaction.user_id)
```

## 🔄 Payment Verification

### Check Payment Status

```python
# Check if payment has been received
payment_status = provider.get_payment_status("payment_123")

if payment_status == "confirmed":
    print("✅ Payment confirmed on blockchain")
    # Get transaction details
    details = provider.get_transaction_details("payment_123")
    print(f"Transaction Hash: {details.get('transaction_hash')}")
    print(f"Confirmations: {details.get('confirmations')}")
elif payment_status == "pending":
    print("⏳ Payment pending confirmation")
else:
    print("❌ Payment not received")
```

### Monitor Transactions

```python
# Monitor blockchain for payments
def monitor_payments():
    while True:
        try:
            # Get recent transactions
            transactions = provider.list_transactions(limit=10)
            
            for tx in transactions:
                if tx['status'] == 'pending':
                    # Check if payment is confirmed
                    if provider.verify_payment(tx['id']):
                        print(f"✅ Payment {tx['id']} confirmed!")
                        # Grant access to AI agent features
                        grant_access(tx['user_id'])
                    elif tx['status'] == 'expired':
                        print(f"❌ Payment {tx['id']} expired")
                        # Handle expired payment
            
            time.sleep(60)  # Check every minute
            
        except Exception as e:
            print(f"Error monitoring payments: {e}")
            time.sleep(60)
```

## 🛡️ Security Features

### Address Validation

```python
from web3 import Web3

# Validate wallet address
def validate_address(address):
    try:
        checksum_address = Web3.to_checksum_address(address)
        return checksum_address
    except Exception as e:
        raise ValueError(f"Invalid wallet address: {e}")

# Use in provider initialization
wallet_address = validate_address("0xYourWalletAddress")
provider = CryptoProvider(
    wallet_address=wallet_address,
    infura_project_id="your_infura_project_id"
)
```

### Gas Price Protection

```python
# Set maximum gas price to prevent overpayment
provider = CryptoProvider(
    wallet_address="0xYourWalletAddress",
    infura_project_id="your_infura_project_id",
    max_gas_price_gwei=100  # Maximum 100 gwei
)

# Check current gas price
network_info = provider.get_network_info()
print(f"Current gas price: {network_info.get('gas_price_gwei')} gwei")
```

## 🔧 Advanced Configuration

### Custom Network Settings

```python
# Custom configuration for production
provider = CryptoProvider(
    wallet_address="0xYourWalletAddress",
    infura_project_id="your_infura_project_id",
    network="mainnet",
    confirmations_required=12,  # Wait for 12 confirmations
    max_gas_price_gwei=100     # Maximum gas price
)

# Get network information
network_info = provider.get_network_info()
print(f"Network: {network_info['name']}")
print(f"Chain ID: {network_info['chain_id']}")
print(f"Block Time: {network_info['block_time']} seconds")
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

## 💸 Refund Process

### Manual Refunds

```python
# Only refund confirmed payments
if provider.verify_payment(transaction.id):
    refund_info = provider.refund_payment(transaction.id, amount=50.0)
    
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

## 🚨 Error Handling

### Common Error Scenarios

```python
try:
    transaction = provider.process_payment(user_id, amount, "USD")
except ProviderError as e:
    if "Invalid wallet address" in str(e):
        print("❌ Check your wallet address format")
    elif "Infura connection failed" in str(e):
        print("❌ Check your Infura project ID and network connectivity")
    elif "Gas price too high" in str(e):
        print("❌ Gas price exceeds maximum limit")
    else:
        print(f"❌ Provider error: {e}")
except PaymentFailed as e:
    print(f"❌ Payment failed: {e}")
except ValidationError as e:
    print(f"❌ Validation error: {e}")
```

### Debug Mode

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# This will show detailed web3 calls and responses
provider = CryptoProvider(
    wallet_address="0xYourWalletAddress",
    infura_project_id="your_infura_project_id",
    network="sepolia"  # Use testnet for debugging
)
```

## 📊 Transaction Management

### List Transactions

```python
# Get all transactions
all_transactions = provider.list_transactions()

# Get transactions for specific user
user_transactions = provider.list_transactions(user_id="user123")

# Get transactions by status
pending_transactions = provider.list_transactions(status="pending")
confirmed_transactions = provider.list_transactions(status="confirmed")

# Get recent transactions with limit
recent_transactions = provider.list_transactions(limit=10)
```

### Transaction Details

```python
# Get detailed transaction information
transaction_details = provider.get_transaction_details("payment_123")

print(f"Transaction ID: {transaction_details['id']}")
print(f"User ID: {transaction_details['user_id']}")
print(f"Amount: {transaction_details['amount']} USD")
print(f"USDT Amount: {transaction_details['usdt_amount']} USDT")
print(f"Status: {transaction_details['status']}")
print(f"Created: {transaction_details['created_at']}")
print(f"Transaction Hash: {transaction_details.get('transaction_hash')}")
print(f"Confirmations: {transaction_details.get('confirmations')}")
```

## 🔄 Migration Guide

### From Old Crypto Provider

If migrating from the old BlockCypher/CoinGecko implementation:

1. **Update Dependencies**:
   ```bash
   pip uninstall blockcypher coingecko
   pip install web3
   ```

2. **Update API Keys**:
   ```bash
   # Remove old keys
   unset BLOCKCYPHER_TOKEN
   unset COINGECKO_API_KEY
   
   # Add new keys
   export INFURA_PROJECT_ID="your_infura_project_id"
   export WALLET_ADDRESS="0xYourWalletAddress"
   ```

3. **Update Code**:
   ```python
   # Old implementation
   provider = CryptoProvider(crypto_type="bitcoin")
   
   # New implementation
   provider = CryptoProvider(
       wallet_address="0xYourWalletAddress",
       infura_project_id="your_infura_project_id",
       network="mainnet"
   )
   ```

4. **Test Thoroughly**: Verify all payment flows work correctly

### From Other Crypto Providers

If migrating from other crypto providers:

1. **Set up Infura**: Create account and get project ID
2. **Configure Wallet**: Ensure wallet address is valid and has ETH for gas
3. **Update Code**: Use new provider interface
4. **Test on Sepolia**: Test thoroughly on testnet before mainnet
5. **Monitor Transactions**: Set up proper monitoring and alerts

## 🛠️ Troubleshooting

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

### Network Status

```python
# Check network status
network_info = provider.get_network_info()
print(f"Network: {network_info['name']}")
print(f"Chain ID: {network_info['chain_id']}")
print(f"Block Height: {network_info['block_height']}")
print(f"Gas Price: {network_info['gas_price_gwei']} gwei")
print(f"Block Time: {network_info['block_time']} seconds")
```

## 📈 Production Considerations

### Wallet Management

- Use hardware wallets for large amounts
- Implement proper key management
- Set up secure wallet infrastructure
- Monitor wallet balances regularly

### Network Monitoring

- Monitor gas fees and network congestion
- Set up alerts for failed transactions
- Track confirmation times
- Monitor Infura rate limits

### Security

- Never expose private keys
- Use environment variables for sensitive data
- Implement proper access controls
- Regular security audits

## 🆘 Support

For issues with the USDT crypto provider:

1. Check this guide for common solutions
2. Review the error messages and logs
3. Verify your Infura project ID and wallet address
4. Test with the provided examples
5. Check network status and gas prices

Remember: The USDT crypto provider is designed for production use with comprehensive security features. For testing, always use the Sepolia testnet first. 