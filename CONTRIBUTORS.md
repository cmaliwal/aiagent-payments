# Contributors

Thanks to all the people who contribute to this project!

- [Chirag Maliwal](https://github.com/cmaliwal)

_You can add yourself here by submitting a pull request!_

## Developer Notes

- The Stripe Python library uses dynamic attributes (e.g., PaymentIntent, Webhook, error, Refund, api_key) that are not visible to static type checkers. We use '# type: ignore[attr-defined]' on these lines to silence false positives from tools like pyright/mypy. This is intentional and required for compatibility.
- The SDK uses config-driven modularity: only enabled providers and storage backends are importable and usable, based on aiagent_payments/config.py or environment variables. This is enforced at the code level for safety and production readiness.

- All fallback/mock modes (e.g., missing Stripe/Crypto libraries) log warnings in production. All error handling is reviewed to ensure no errors are swallowed silently. Generic 'except Exception' blocks are always logged and re-raised or wrapped in custom exceptions. 