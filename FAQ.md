# AI Agent Payments SDK – Frequently Asked Questions (FAQ)

## General

**Q: What is the AI Agent Payments SDK?**
A: It's a plug-and-play Python SDK for monetizing AI/autonomous agents with subscriptions, pay-per-use, access control, quotas, and payment verification. It supports Stripe, PayPal, crypto, and mock providers.

**Q: Who should use this SDK?**
A: Developers building AI/agent-based apps, APIs, or bots who want to add flexible, secure payment and access control.

---

## Payments & Integration

**Q: How does a user make a payment?**
A: The SDK enforces access and raises a `PaymentRequired` exception when payment is needed. You (the developer) integrate with a payment provider's UI (Stripe Checkout, PayPal, crypto wallet, etc.), and after payment, call the SDK to activate access or record usage.

**Q: Does the SDK provide a payment UI?**
A: No. The SDK is backend-focused. You design your own payment UI and call the SDK after payment is complete.

**Q: How do I handle subscriptions?**
A: After a successful payment, call `subscribe_user(user_id, plan_id)`. The SDK tracks and enforces access.

**Q: How do I handle pay-per-use?**
A: After payment, call `process_payment(user_id, amount, ...)` and credit usage. The SDK enforces quotas and access.

**Q: Can I use webhooks for automated payment updates?**
A: Yes! Implement webhook endpoints in your app and use the SDK's verification stubs to validate events from Stripe/PayPal/etc.

---

## Provider/Storage Configuration

**Q: How do I enable or disable payment providers or storage backends?**
A: Edit `aiagent_payments/config.py` or set environment variables to control which providers/storage are enabled. Only enabled providers/storage are importable and usable; others will raise errors if used.

**Q: What happens if I try to use a disabled provider or storage backend?**
A: The SDK will raise an error and log a warning. This ensures only approved providers/storage are used in your environment.

**Q: How do I configure PayPal with return URLs and webhooks?**
A: Use the factory function with all required parameters: `create_payment_provider("paypal", client_id="...", client_secret="...", return_url="...", cancel_url="...", webhook_id="...")`. All parameters are properly forwarded to the PayPal provider.

---

## API Keys & Security

**Q: Do I need API keys for Stripe, PayPal, or Crypto?**
A: Yes. For production use, you must supply your own API keys for Stripe, PayPal, and Crypto providers. The SDK will not function in production without them. For local/dev/demo, you can use mock mode or public endpoints (with warnings).

**Q: How does the SDK keep payments secure?**
A: It never logs secrets, enforces strict input validation, redacts sensitive data in logs, and provides webhook signature verification stubs. You should always use HTTPS and secure your environment variables.

**Q: Is my data safe?**
A: The SDK supports secure storage and recommends encryption and restrictive permissions for sensitive deployments.

---

## Extensibility & Customization

**Q: Can I add my own payment provider?**
A: Yes! Implement the `PaymentProvider` interface in `aiagent_payments/providers/` and register it in the config.

**Q: Can I use a custom storage backend?**
A: Yes! Implement the `StorageBackend` interface in `aiagent_payments/storage/` and register it in the config.

---

## Compliance & Legal

**Q: What are my compliance responsibilities?**
A: You are responsible for ensuring your use of the SDK complies with all laws, regulations, and payment provider terms. See the [DISCLAIMER.md](DISCLAIMER.md) for details.

---

## Troubleshooting

**Q: I get a `PaymentRequired` or `UsageLimitExceeded` error. What do I do?**
A: Prompt the user to pay or upgrade, process the payment, and call the SDK to update their access.

**Q: I see a warning about `datetime.utcnow()` being deprecated.**
A: The SDK now uses timezone-aware datetimes and is future-proof for Python 3.12+.

**Q: PayPal provider shows "return_url cannot be empty" error.**
A: Make sure you're passing `return_url` and `cancel_url` to the factory function: `create_payment_provider("paypal", ..., return_url="...", cancel_url="...")`. The factory now properly forwards these parameters.

**Q: Crypto provider shows "In-memory storage not allowed in production mode" error.**
A: Set the environment variable `AIAgentPayments_DevMode=1` for development/testing, or use a proper storage backend like `DatabaseStorage` or `FileStorage` for production.

**Q: How do I get help or report a bug?**
A: Open an issue on the GitHub repo or contact the maintainers.

---

## Recent Updates

**Q: What was fixed in the latest update?**
A: The PayPal provider factory function now properly forwards `return_url`, `cancel_url`, `webhook_id`, and `timeout` parameters to the PayPal provider constructor. This fixes configuration issues when using the factory pattern.

---

## More Questions?
If you have more questions, open an issue or start a discussion on GitHub! 