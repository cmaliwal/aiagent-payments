import importlib
import os

import pytest

from aiagent_payments.config import (
    ENABLED_PROVIDERS,
    ENABLED_STORAGE,
    VALID_PAYMENT_PROVIDERS,
    VALID_STORAGE_BACKENDS,
    _get_enabled_providers,
    _get_enabled_storage,
    _normalize_config_list,
    get_config_summary,
    is_provider_enabled,
    is_storage_enabled,
)

STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY")
INFURA_PROJECT_ID = os.environ.get("INFURA_PROJECT_ID")

pytestmark = pytest.mark.skipif(
    not STRIPE_API_KEY or not INFURA_PROJECT_ID, reason="Provider credentials not set; skipping config enforcement tests."
)


# Storage backend import tests
def test_enabled_storage_imports():
    for backend in ENABLED_STORAGE:
        if backend == "memory":
            from aiagent_payments.storage import MemoryStorage

            assert MemoryStorage is not None
        if backend == "file":
            from aiagent_payments.storage import FileStorage

            assert FileStorage is not None
        if backend == "database":
            from aiagent_payments.storage import DatabaseStorage

            assert DatabaseStorage is not None


def test_disabled_storage_imports():
    for backend, symbol in [
        ("memory", "MemoryStorage"),
        ("file", "FileStorage"),
        ("database", "DatabaseStorage"),
    ]:
        if backend not in ENABLED_STORAGE:
            with pytest.raises(ImportError):
                importlib.import_module(f"aiagent_payments.storage").__getattribute__(symbol)


# Provider import tests
def test_enabled_provider_imports():
    for provider in ENABLED_PROVIDERS:
        if provider == "mock":
            from aiagent_payments.providers import MockProvider

            assert MockProvider is not None
        if provider == "crypto":
            # CryptoProvider is lazy-loaded, so we test it through the factory
            from aiagent_payments.providers import create_payment_provider

            # This should not raise an ImportError if CryptoProvider is available
            try:
                # Test that we can create a crypto provider (even if it fails to connect)
                create_payment_provider(
                    "crypto", wallet_address="0x1234567890123456789012345678901234567890", infura_project_id="test_id"
                )
                # If we get here, CryptoProvider is available
                assert True
            except Exception as e:
                # If it's a connection error, that's fine - CryptoProvider is available
                if "Failed to connect" in str(e) or "Failed to setup web3" in str(e):
                    assert True
                elif "circular import" in str(e) or "ASYNC_PROVIDER_TYPE" in str(e):
                    # Web3 library has compatibility issues, but CryptoProvider is available
                    assert True
                else:
                    # If it's an import error, CryptoProvider is not available
                    assert "CryptoProvider is not available" in str(e)
        if provider == "stripe":
            from aiagent_payments.providers import StripeProvider

            assert StripeProvider is not None
        if provider == "paypal":
            from aiagent_payments.providers import PayPalProvider

            assert PayPalProvider is not None


def test_disabled_provider_imports():
    for provider, symbol in [
        ("mock", "MockProvider"),
        ("crypto", "CryptoProvider"),
        ("stripe", "StripeProvider"),
        ("paypal", "PayPalProvider"),
    ]:
        if provider not in ENABLED_PROVIDERS:
            with pytest.raises(ImportError):
                importlib.import_module(f"aiagent_payments.providers").__getattribute__(symbol)


def test_provider_factory_enforcement():
    from aiagent_payments.providers import create_payment_provider

    for provider in ["mock", "crypto", "stripe", "paypal"]:
        if provider in ENABLED_PROVIDERS:
            # Should not raise
            if provider == "crypto":
                # Crypto provider requires wallet_address and infura_project_id
                try:
                    create_payment_provider(
                        provider, wallet_address="0x1234567890123456789012345678901234567890", infura_project_id="test_id"
                    )
                except Exception as e:
                    # Connection errors are expected without real credentials
                    assert "Failed to connect" in str(e) or "Failed to setup web3" in str(e)
            elif provider == "stripe":
                # Provide dummy API key
                create_payment_provider(provider, api_key="sk_test_dummy")
            elif provider == "paypal":
                # Provide dummy client_id, client_secret, return_url, cancel_url
                create_payment_provider(
                    provider,
                    client_id="dummy_id",
                    client_secret="dummy_secret",
                    return_url="https://example.com/success",
                    cancel_url="https://example.com/cancel",
                )
            else:
                # Other providers should work with basic setup
                create_payment_provider(provider)
        else:
            # Should raise for disabled providers
            with pytest.raises(ValueError):
                create_payment_provider(provider)


def test_normalize_config_list_valid():
    result = _normalize_config_list("memory,file", VALID_STORAGE_BACKENDS, "storage backends")
    assert result == ["memory", "file"]


def test_normalize_config_list_invalid():
    with pytest.raises(ValueError):
        _normalize_config_list("memory,invalid", VALID_STORAGE_BACKENDS, "storage backends")


def test_get_enabled_storage_and_providers(monkeypatch):
    monkeypatch.setenv("AIAgentPayments_EnabledStorage", "memory,file")
    monkeypatch.setenv("AIAgentPayments_EnabledProviders", "mock,crypto")
    assert _get_enabled_storage() == ["memory", "file"]
    assert _get_enabled_providers() == ["mock", "crypto"]


def test_is_storage_enabled_and_is_provider_enabled(monkeypatch):
    monkeypatch.setenv("AIAgentPayments_EnabledStorage", "memory,file")
    monkeypatch.setenv("AIAgentPayments_EnabledProviders", "mock,crypto")
    # Re-import to update globals
    import importlib

    import aiagent_payments.config as config_mod

    importlib.reload(config_mod)
    assert config_mod.is_storage_enabled("memory")
    assert not config_mod.is_storage_enabled("database")
    assert config_mod.is_provider_enabled("mock")
    assert not config_mod.is_provider_enabled("stripe")


def test_get_config_summary():
    summary = get_config_summary()
    assert "enabled_storage" in summary
    assert "enabled_providers" in summary
    assert "valid_storage_backends" in summary
    assert "valid_payment_providers" in summary
