import pytest

from aiagent_payments.exceptions import (
    AccessControlError,
    AIAgentPaymentsError,
    ConfigurationError,
    FeatureNotAvailable,
    InvalidPaymentMethod,
    PaymentError,
    PaymentFailed,
    PaymentRequired,
    ProviderError,
    StorageError,
    SubscriptionExpired,
    UsageLimitExceeded,
    ValidationError,
)


def test_aiagent_payments_error_str():
    err = AIAgentPaymentsError("msg", error_code="E1", details={"foo": "bar"})
    assert str(err) == "[E1] msg"
    assert err.details["foo"] == "bar"


def test_payment_failed_details():
    err = PaymentFailed("fail", transaction_id="tx1", provider_error="err1")
    assert err.details["transaction_id"] == "tx1"
    assert err.details["provider_error"] == "err1"
    assert err.error_code == "PAYMENT_FAILED"


def test_payment_required_details():
    err = PaymentRequired("pay", feature="f", required_amount=10.0)
    assert err.details["feature"] == "f"
    assert err.details["required_amount"] == 10.0
    assert err.error_code == "PAYMENT_REQUIRED"


def test_invalid_payment_method_details():
    err = InvalidPaymentMethod("bad", payment_method="pm", supported_methods=["a"])
    assert err.details["payment_method"] == "pm"
    assert err.details["supported_methods"] == ["a"]
    assert err.error_code == "INVALID_PAYMENT_METHOD"


def test_access_control_error_code():
    err = AccessControlError("access")
    assert err.error_code == "ACCESS_CONTROL_ERROR"


def test_usage_limit_exceeded_details():
    err = UsageLimitExceeded("limit", feature="f", current_usage=5, limit=3)
    assert err.details["feature"] == "f"
    assert err.details["current_usage"] == 5
    assert err.details["limit"] == 3


def test_subscription_expired_details():
    err = SubscriptionExpired("expired", subscription_id="s", plan_id="p", expired_date="d")
    assert err.details["subscription_id"] == "s"
    assert err.details["plan_id"] == "p"
    assert err.details["expired_date"] == "d"


def test_feature_not_available_details():
    err = FeatureNotAvailable("notavail", feature="f", plan_id="p", available_features=["a"])
    assert err.details["feature"] == "f"
    assert err.details["plan_id"] == "p"
    assert err.details["available_features"] == ["a"]


def test_storage_error_details():
    err = StorageError("storage", storage_type="t", operation="op", entity_id="id")
    assert err.details["storage_type"] == "t"
    assert err.details["operation"] == "op"
    assert err.details["entity_id"] == "id"


def test_configuration_error_details():
    err = ConfigurationError("config", config_key="k", expected_value="e", actual_value="a")
    assert err.details["config_key"] == "k"
    assert err.details["expected_value"] == "e"
    assert err.details["actual_value"] == "a"


def test_validation_error_details():
    err = ValidationError("val", field="f", value=1, constraints={"c": 2})
    assert err.details["field"] == "f"
    assert err.details["value"] == 1
    assert err.details["constraints"]["c"] == 2


def test_provider_error_details():
    err = ProviderError("prov", provider="p", provider_error_code="e", provider_error_message="m")
    assert err.details["provider"] == "p"
    assert err.details["provider_error_code"] == "e"
    assert err.details["provider_error_message"] == "m"
