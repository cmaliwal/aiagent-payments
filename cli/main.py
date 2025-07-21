"""
Command-line interface for AI Agent Payments SDK.
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from enum import Enum

from aiagent_payments import PaymentManager, PaymentPlan
from aiagent_payments.config import ENABLED_PROVIDERS, ENABLED_STORAGE
from aiagent_payments.exceptions import ConfigurationError, PaymentFailed, ValidationError
from aiagent_payments.models import BillingPeriod, PaymentType
from aiagent_payments.providers import create_payment_provider
from aiagent_payments.storage import DatabaseStorage, FileStorage, MemoryStorage


def create_payment_manager(args: argparse.Namespace) -> PaymentManager:
    if args.storage not in ENABLED_STORAGE:
        raise ValueError(f"Storage backend '{args.storage}' is disabled in configuration.")
    if args.storage == "memory":
        storage = MemoryStorage()
    elif args.storage == "file":
        storage = FileStorage(args.storage_path)
    elif args.storage == "database":
        storage = DatabaseStorage(args.storage_path)
    else:
        raise ValueError(f"Unknown storage type: {args.storage}")
    if args.payment_provider not in ENABLED_PROVIDERS:
        raise ValueError(f"Payment provider '{args.payment_provider}' is disabled in configuration.")
    if args.payment_provider == "mock":
        payment_provider = create_payment_provider("mock")
    elif args.payment_provider == "crypto":
        if not args.wallet_address:
            raise ConfigurationError("wallet_address is required for crypto provider.")
        if not getattr(args, "infura_project_id", None):
            raise ConfigurationError("infura_project_id is required for crypto provider.")
        payment_provider = create_payment_provider(
            "crypto",
            wallet_address=args.wallet_address,
            infura_project_id=args.infura_project_id,
        )
    elif args.payment_provider == "stripe":
        if not args.stripe_key:
            raise ConfigurationError("stripe_key is required for stripe provider.")
        payment_provider = create_payment_provider("stripe", api_key=args.stripe_key)
    elif args.payment_provider == "paypal":
        # Optionally require return_url and cancel_url for PayPal
        kwargs = {}
        if getattr(args, "return_url", None):
            kwargs["return_url"] = args.return_url
        if getattr(args, "cancel_url", None):
            kwargs["cancel_url"] = args.cancel_url
        payment_provider = create_payment_provider("paypal", **kwargs)
    else:
        raise ValueError(f"Unknown payment provider: {args.payment_provider}")
    return PaymentManager(
        storage=storage,
        payment_provider=payment_provider,
        default_plan=args.default_plan,
    )


def setup_default_plans(pm: PaymentManager) -> None:
    try:
        freemium_plan = PaymentPlan(
            id="freemium",
            name="Freemium",
            description="Free tier with limited usage",
            payment_type=PaymentType.FREEMIUM,
            price=0.0,
            free_requests=10,
            features=["basic_ai_response", "simple_analysis"],
        )
        pro_plan = PaymentPlan(
            id="pro",
            name="Pro Subscription",
            description="Professional subscription with unlimited usage",
            payment_type=PaymentType.SUBSCRIPTION,
            price=29.99,
            billing_period=BillingPeriod.MONTHLY,
            requests_per_period=1000,
            features=["advanced_ai_response", "complex_analysis", "priority_support"],
        )
        pay_per_use_plan = PaymentPlan(
            id="pay_per_use",
            name="Pay per Use",
            description="Pay only for what you use",
            payment_type=PaymentType.PAY_PER_USE,
            price=0.01,
            price_per_request=0.01,
            features=["all_features"],
        )
        pm.create_payment_plan(freemium_plan)
        pm.create_payment_plan(pro_plan)
        pm.create_payment_plan(pay_per_use_plan)
        print("Default payment plans created:")
        print("- freemium: Free tier with 10 requests")
        print("- pro: $29.99/month with 1000 requests")
        print("- pay_per_use: $0.01 per request")
    except ValidationError as e:
        print(f"Validation error creating default plans: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error creating default plans: {e}")
        sys.exit(1)


def cmd_setup(args: argparse.Namespace) -> None:
    try:
        pm = create_payment_manager(args)
        setup_default_plans(pm)
        print("Payment system setup complete!")
    except (ValidationError, ConfigurationError, PaymentFailed) as e:
        print(f"Setup error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


def cmd_subscribe(args: argparse.Namespace) -> None:
    try:
        pm = create_payment_manager(args)
        subscription = pm.subscribe_user(args.user_id, args.plan_id)
        print(f"User {args.user_id} subscribed to plan {args.plan_id}")
        print(f"Subscription ID: {subscription.id}")
        print(f"Status: {subscription.status}")
    except (ValidationError, ConfigurationError, PaymentFailed) as e:
        print(f"Subscription error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


def cmd_usage(args: argparse.Namespace) -> None:
    try:
        pm = create_payment_manager(args)
        end_date = datetime.now(timezone.utc)
        if args.days:
            start_date = end_date - timedelta(days=args.days)
        else:
            start_date = None
        usage_records = pm.get_user_usage(args.user_id, start_date, end_date)
        print(f"Usage for user {args.user_id}:")
        print(f"Total records: {len(usage_records)}")
        if usage_records:
            total_cost = sum(r.cost or 0 for r in usage_records)
            print(f"Total cost: ${total_cost:.2f}")
            feature_usage = {}
            for record in usage_records:
                feature = record.feature
                if feature not in feature_usage:
                    feature_usage[feature] = 0
                feature_usage[feature] += 1
            print("\nUsage by feature:")
            for feature, count in feature_usage.items():
                print(f"  {feature}: {count} uses")
        else:
            print("No usage records found.")
    except (ValidationError, ConfigurationError, PaymentFailed) as e:
        print(f"Usage error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


def cmd_plans(args: argparse.Namespace) -> None:
    try:
        pm = create_payment_manager(args)
        plans = pm.list_payment_plans()
        print("Available payment plans:")
        for plan in plans:
            print(f"\n{plan.name} ({plan.id}):")
            print(f"  Description: {plan.description}")
            payment_type = plan.payment_type.value if isinstance(plan.payment_type, Enum) else str(plan.payment_type)
            print(f"  Type: {payment_type}")
            print(f"  Price: ${plan.price}")
            if plan.payment_type == PaymentType.PAY_PER_USE:
                print(f"  Price per request: ${plan.price_per_request}")
            elif plan.payment_type == PaymentType.SUBSCRIPTION:
                if plan.billing_period:
                    billing_period = (
                        plan.billing_period.value if isinstance(plan.billing_period, Enum) else str(plan.billing_period)
                    )
                    print(f"  Billing period: {billing_period}")
                if plan.requests_per_period:
                    print(f"  Requests per period: {plan.requests_per_period}")
            elif plan.payment_type == PaymentType.FREEMIUM:
                print(f"  Free requests: {plan.free_requests}")
            if plan.features:
                print(f"  Features: {', '.join(plan.features)}")
    except (ValidationError, ConfigurationError, PaymentFailed) as e:
        print(f"Plans error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


def cmd_status(args: argparse.Namespace) -> None:
    try:
        pm = create_payment_manager(args)
        subscription = pm.get_user_subscription(args.user_id)
        print(f"Status for user {args.user_id}:")
        if subscription:
            plan = pm.get_payment_plan(subscription.plan_id)
            print(f"  Plan: {plan.name if plan else subscription.plan_id}")
            print(f"  Status: {subscription.status}")
            print(f"  Usage this period: {subscription.usage_count}")
            if subscription.current_period_end:
                period_end = subscription.current_period_end
                if isinstance(period_end, datetime):
                    period_end_str = period_end.isoformat()
                else:
                    period_end_str = str(period_end)
                print(f"  Period ends: {period_end_str}")
            if subscription.is_active():
                print("  ✅ Subscription is active")
            else:
                print("  ❌ Subscription is not active")
        else:
            print("  No active subscription")
        print("\nFeature access:")
        features = ["basic_ai_response", "advanced_ai_response", "complex_analysis"]
        for feature in features:
            has_access = pm.check_access(args.user_id, feature)
            status = "✅" if has_access else "❌"
            print(f"  {feature}: {status}")
    except (ValidationError, ConfigurationError, PaymentFailed) as e:
        print(f"Status error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI Agent Payments SDK Command Line Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s setup --storage file --payment-provider mock
  %(prog)s subscribe user123 pro
  %(prog)s usage user123 --days 30
  %(prog)s plans
  %(prog)s status user123
        """,
    )
    parser.add_argument(
        "--storage",
        choices=ENABLED_STORAGE,
        default=ENABLED_STORAGE[0] if ENABLED_STORAGE else "memory",
        help="Storage backend to use",
    )
    parser.add_argument("--storage-path", default="payments_data", help="Path for file/database storage")
    parser.add_argument(
        "--payment-provider",
        choices=ENABLED_PROVIDERS,
        default=ENABLED_PROVIDERS[0] if ENABLED_PROVIDERS else "mock",
        help="Payment provider to use",
    )
    parser.add_argument("--wallet-address", help="Crypto wallet address")
    parser.add_argument("--infura-project-id", help="Infura project ID for crypto provider")
    parser.add_argument("--stripe-key", help="Stripe API key")
    parser.add_argument("--return-url", help="PayPal return URL")
    parser.add_argument("--cancel-url", help="PayPal cancel URL")
    parser.add_argument("--default-plan", help="Default payment plan ID")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    setup_parser = subparsers.add_parser("setup", help="Set up payment system")
    setup_parser.set_defaults(func=cmd_setup)
    subscribe_parser = subparsers.add_parser("subscribe", help="Subscribe user to plan")
    subscribe_parser.add_argument("user_id", help="User ID")
    subscribe_parser.add_argument("plan_id", help="Plan ID")
    subscribe_parser.set_defaults(func=cmd_subscribe)
    usage_parser = subparsers.add_parser("usage", help="Show user usage")
    usage_parser.add_argument("user_id", help="User ID")
    usage_parser.add_argument("--days", type=int, help="Number of days to look back")
    usage_parser.set_defaults(func=cmd_usage)
    plans_parser = subparsers.add_parser("plans", help="List payment plans")
    plans_parser.set_defaults(func=cmd_plans)
    status_parser = subparsers.add_parser("status", help="Show user status")
    status_parser.add_argument("user_id", help="User ID")
    status_parser.set_defaults(func=cmd_status)
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    try:
        args.func(args)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
