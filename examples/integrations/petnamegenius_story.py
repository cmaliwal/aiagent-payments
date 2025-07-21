"""
PetNameGenius: Fun AI Pet Name Generator SaaS Example

Story:
Jamie, a solo founder, built 'PetNameGenius'—an AI-powered web app that generates creative pet names. Jamie wants to monetize the app:
- Free users: 3 name generations per day
- Paid users: Unlimited names, premium features

This example shows how to use aiagent_payments to handle subscriptions, pay-per-use, and access control.
"""

import random

from aiagent_payments import PaymentManager, PaymentPlan
from aiagent_payments.models import BillingPeriod, PaymentType
from aiagent_payments.providers import create_payment_provider
from aiagent_payments.storage import MemoryStorage

# --- Setup ---
# Define payment plans
free_plan = PaymentPlan(
    id="free",
    name="Free Plan",
    description="Free plan with 3 pet name generations per month",
    payment_type=PaymentType.FREEMIUM,
    price=0.01,  # Minimum price required by validation
    currency="USD",
    billing_period=BillingPeriod.MONTHLY,
    requests_per_period=3,
    free_requests=3,
    features=["basic_names"],
)
premium_plan = PaymentPlan(
    id="premium",
    name="Premium Plan",
    description="Unlimited pet names and premium features",
    payment_type=PaymentType.SUBSCRIPTION,
    price=9.99,
    currency="USD",
    billing_period=BillingPeriod.MONTHLY,
    requests_per_period=None,
    free_requests=0,
    features=["basic_names", "breed_specific", "unlimited"],
)

# Choose provider (mock for demo)
payment_provider = create_payment_provider("mock")
# Use in-memory storage for demo
storage = MemoryStorage()

# Create payment manager
manager = PaymentManager(
    storage=storage,
    payment_provider=payment_provider,
)

# Register payment plans
manager.create_payment_plan(free_plan)
manager.create_payment_plan(premium_plan)


# --- Demo User Flow ---
def generate_pet_name(breed=None):
    names = ["Fluffy", "Shadow", "Milo", "Luna", "Bella", "Simba", "Coco", "Rocky"]
    if breed:
        return f"{random.choice(names)} the {breed.title()}"
    return random.choice(names)


# Decorated feature functions
def make_basic_name(user_id):
    name = generate_pet_name()
    print(f"[Free] Pet name suggestion: {name}")


make_basic_name = manager.paid_feature(feature_name="basic_names")(make_basic_name)


def make_breed_specific_name(user_id, breed):
    name = generate_pet_name(breed=breed)
    print(f"[Premium] Pet name suggestion for {breed}: {name}")


make_breed_specific_name = manager.paid_feature(feature_name="breed_specific")(make_breed_specific_name)

user_id = "jamie@example.com"

# User signs up for free plan
token = manager.subscribe_user(user_id, plan_id="free")
print(f"User {user_id} subscribed to Free Plan. Token: {token}")

# User tries to generate pet names (should be limited)
for i in range(5):
    try:
        make_basic_name(user_id)
    except Exception as e:
        print(f"[Free] Attempt {i + 1}: {e}")

# User upgrades to premium
manager.subscribe_user(user_id, plan_id="premium")
print(f"User {user_id} upgraded to Premium Plan.")

# User now gets unlimited, breed-specific names
for breed in ["poodle", "bulldog", "siamese"]:
    make_breed_specific_name(user_id, breed)
