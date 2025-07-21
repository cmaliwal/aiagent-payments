import pytest

from aiagent_payments.utils import (
    deep_get,
    deep_set,
    format_currency,
    generate_id,
    get_current_timestamp,
    parse_datetime,
    parse_email,
    retry,
    sanitize_string,
    validate_amount,
    validate_currency,
)


def test_retry_success():
    calls = []

    @retry(max_attempts=3)
    def f():
        calls.append(1)
        return 42

    assert f() == 42
    assert len(calls) == 1


def test_retry_on_exception():
    calls = []

    @retry(exceptions=RuntimeError, max_attempts=3, initial_delay=0.01)
    def f():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("fail")
        return 99

    assert f() == 99
    assert len(calls) == 3


def test_retry_gives_up():
    calls = []

    @retry(exceptions=RuntimeError, max_attempts=2, initial_delay=0.01)
    def f():
        calls.append(1)
        raise RuntimeError("fail")

    with pytest.raises(RuntimeError):
        f()
    assert len(calls) == 2


def test_generate_id():
    id1 = generate_id()
    id2 = generate_id("prefix-")
    assert isinstance(id1, str) and len(id1) > 0
    assert id2.startswith("prefix-")


def test_validate_currency():
    assert validate_currency("USD")
    assert not validate_currency("usd")
    assert not validate_currency("US")


def test_validate_amount():
    assert validate_amount(10)
    assert validate_amount(0.0)
    assert not validate_amount(-1)
    assert not validate_amount(float("nan"))


def test_format_currency():
    assert format_currency(10, "USD") == "10.00 USD"
    assert format_currency(-1, "USD") == "Invalid amount/currency"
    assert format_currency(10, "usd") == "Invalid amount/currency"


def test_parse_datetime():
    dt = parse_datetime("2024-01-01T12:00:00+00:00")
    assert dt and dt.year == 2024
    assert parse_datetime("invalid") is None


def test_get_current_timestamp():
    ts = get_current_timestamp()
    assert ts.tzinfo is not None


def test_parse_email():
    assert parse_email("test@example.com") == "test@example.com"
    assert parse_email("invalid") is None


def test_sanitize_string():
    assert sanitize_string("abc", 2) == "ab"
    assert sanitize_string(None) == ""


def test_deep_get_and_set():
    d = {}
    deep_set(d, "a.b.c", 42)
    assert deep_get(d, "a.b.c") == 42
    assert deep_get(d, "a.b.x", default=99) == 99
