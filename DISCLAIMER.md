# Disclaimer & Terms of Use

This SDK enables integration with real money and cryptocurrency payment providers (e.g., Stripe, PayPal, crypto APIs). By using this SDK, you acknowledge and agree to the following:

## No Warranty or Liability
- This SDK is provided "as is" and without warranty of any kind, express or implied.
- The maintainers and contributors are not liable for any loss, damages, or legal issues arising from the use of this SDK in production or financial environments.

## Compliance is Your Responsibility
- You are solely responsible for ensuring that your use of this SDK complies with all applicable laws, regulations, and payment provider terms (including but not limited to Stripe, PayPal, and crypto services).
- This includes, but is not limited to:
  - **KYC/AML:** Know Your Customer and Anti-Money Laundering regulations may apply, especially for crypto payments.
  - **PCI DSS:** If you handle credit card data directly (not recommended), you must comply with PCI DSS standards.
  - **Data Privacy:** You must comply with all applicable data privacy laws (e.g., GDPR, CCPA) if you store or process user data.
  - **Provider Terms:** You must follow the terms of service for all payment providers and APIs you use, including Stripe, PayPal, and crypto APIs.

## API Keys & Production Use
- For production use of Stripe, PayPal, and Crypto providers, you must supply your own API keys. The SDK will not function in production without them.
- Fallback/mock modes are for development and testing only. They log warnings in production and are not suitable for real payments.

## No Legal or Compliance Advice
- This SDK and its documentation do not constitute legal, financial, or compliance advice.
- You should consult with qualified legal and compliance professionals before using this SDK in any production or financial context.

## Contributions
- By contributing to this project, you agree that your contributions do not violate any applicable laws or third-party rights.

## Summary
- Use this SDK at your own risk.
- Ensure you understand and comply with all relevant legal and regulatory requirements before going live with real payments. 