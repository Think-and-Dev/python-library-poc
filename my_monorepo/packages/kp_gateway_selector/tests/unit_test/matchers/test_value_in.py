import pytest
from kp_gateway_selector.gateway_selector.matchers.value_in import ValueIn, make_value_in

def test_value_in_str_representation():
    """
    Tests the __str__ representation of the ValueIn matcher.
    """
    matcher = ValueIn(field="test_field", values=frozenset([1, 2, 3]), coerce="int")
    expected_str = "VALUE_IN(field=test_field, values=frozenset({1, 2, 3}), coerce=int)"
    assert str(matcher) == expected_str

def test_make_value_in_success():
    cond = {"field": "api_user_id", "values": [101, 102, 103], "coerce": "int"}
    matcher = make_value_in(cond)
    assert isinstance(matcher, ValueIn)
    assert matcher.field == "api_user_id"
    assert matcher.values == frozenset([101, 102, 103])
    assert matcher.coerce == "int"

def test_make_value_in_invalid_field():
    with pytest.raises(ValueError, match="VALUE_IN: field str y values list requeridos"):
        make_value_in({"field": 123, "values": []})

def test_make_value_in_invalid_values():
    with pytest.raises(ValueError, match="VALUE_IN: field str y values list requeridos"):
        make_value_in({"field": "a", "values": {}})

def test_make_value_in_invalid_coerce():
    with pytest.raises(ValueError, match="VALUE_IN: coerce inválido"):
        make_value_in({"field": "a", "values": [], "coerce": "invalid"})

def test_value_in_call_success():
    matcher = ValueIn(field="user.id", values=frozenset([1, 2, 3]), coerce="int")
    assert matcher({"user": {"id": "1"}}) is True
    assert matcher({"user": {"id": "4"}}) is False

def test_value_in_call_no_coerce():
    matcher = ValueIn(field="user.id", values=frozenset(["a", "b"]), coerce=None)
    assert matcher({"user": {"id": "a"}}) is True
    assert matcher({"user": {"id": "c"}}) is False

def test_value_in_call_lower_str():
    matcher = ValueIn(field="user.name", values=frozenset(["admin", "guest"]), coerce="lower-str")
    assert matcher({"user": {"name": "Admin"}}) is True
    assert matcher({"user": {"name": "Guest"}}) is True
    assert matcher({"user": {"name": "Other"}}) is False

def test_value_in_call_field_not_found():
    matcher = ValueIn(field="user.id", values=frozenset([1, 2, 3]), coerce="int")
    assert matcher({}) is False
    assert matcher({"user": {}}) is False

def test_value_in_call_coerce_error():
    matcher = ValueIn(field="user.id", values=frozenset([1, 2, 3]), coerce="int")
    assert matcher({"user": {"id": "not-a-number"}}) is False