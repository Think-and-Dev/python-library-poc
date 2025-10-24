import pytest
from decimal import Decimal
from kp_gateway_selector.gateway_selector.matchers.amount_range import (
    _to_decimal,
    make_amount_range,
    AmountRange,
)


def test_to_decimal_valid():
    assert _to_decimal("123.45") == Decimal("123.45")


def test_to_decimal_none():
    assert _to_decimal(None) is None


def test_to_decimal_invalid():
    assert _to_decimal("abc") is None


def test_make_amount_range_valid():
    cond = {"type": "AMOUNT_RANGE", "field": "amount", "min": "10", "max": "100"}
    matcher = make_amount_range(cond)
    assert isinstance(matcher, AmountRange)


def test_make_amount_range_invalid_field():
    with pytest.raises(ValueError, match="field debe ser string"):
        make_amount_range({"field": 123})


def test_make_amount_range_invalid_coerce():
    with pytest.raises(ValueError, match="coerce inválido"):
        make_amount_range({"coerce": "invalid"})


def test_make_amount_range_invalid_scale():
    with pytest.raises(ValueError, match="scale debe ser >= 0"):
        make_amount_range({"scale": -1})


def test_make_amount_range_invalid_min_max():
    with pytest.raises(ValueError, match="min inválido"):
        make_amount_range({"min": "abc"})
    with pytest.raises(ValueError, match="max inválido"):
        make_amount_range({"max": "abc"})


def test_make_amount_range_max_less_than_min():
    with pytest.raises(ValueError, match="max < min"):
        make_amount_range({"min": "100", "max": "10"})


def test_amount_range_call_no_field():
    matcher = AmountRange("f", "decimal", 0, None, None, True, True)
    assert matcher({}) is False


def test_amount_range_call_coerce_int():
    matcher = AmountRange("f", "int", 2, None, None, True, True)
    assert matcher({"f": 12345}) is True


def test_amount_range_call_coerce_int_invalid():
    matcher = AmountRange("f", "int", 2, None, None, True, True)
    assert matcher({"f": "abc"}) is False


def test_amount_range_call_coerce_decimal():
    matcher = AmountRange("f", "decimal", 0, None, None, True, True)
    assert matcher({"f": "123.45"}) is True


def test_amount_range_call_coerce_decimal_invalid():
    matcher = AmountRange("f", "decimal", 0, None, None, True, True)
    assert matcher({"f": "abc"}) is False


def test_amount_range_call_min_inclusive():
    matcher = AmountRange("f", "decimal", 0, Decimal("10"), None, True, True)
    assert matcher({"f": "10"}) is True
    assert matcher({"f": "9.9"}) is False


def test_amount_range_call_min_exclusive():
    matcher = AmountRange("f", "decimal", 0, Decimal("10"), None, False, True)
    assert matcher({"f": "10"}) is False
    assert matcher({"f": "10.1"}) is True


def test_amount_range_call_max_inclusive():
    matcher = AmountRange("f", "decimal", 0, None, Decimal("100"), True, True)
    assert matcher({"f": "100"}) is True
    assert matcher({"f": "100.1"}) is False


def test_amount_range_call_max_exclusive():
    matcher = AmountRange("f", "decimal", 0, None, Decimal("100"), True, False)
    assert matcher({"f": "100"}) is False
    assert matcher({"f": "99.9"}) is True

def test_amount_range_name_property():
    """
    Tests the name property of the AmountRange matcher.
    """
    matcher = AmountRange("f", "decimal", 0, None, None, True, True)
    assert matcher.name == "AMOUNT_RANGE"

def test_amount_range_str_representation():
    """
    Tests the __str__ representation of the AmountRange matcher.
    """
    matcher = AmountRange(
        field="amount",
        coerce="decimal",
        scale=2,
        min_v=Decimal("10.00"),
        max_v=Decimal("100.00"),
        min_inclusive=True,
        max_inclusive=False,
    )
    expected_str = "AMOUNT_RANGE(field=amount, coerce=decimal, scale=2, min_v=10.00, max_v=100.00, min_inclusive=True, max_inclusive=False)"
    assert str(matcher) == expected_str