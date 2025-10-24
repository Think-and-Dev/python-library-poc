import pytest
import re
import sys
from unittest.mock import Mock
from kp_gateway_selector.gateway_selector.matchers.regex import (
    _compose_flags,
    make_regex,
    RegexMatcher,
)


def test_compose_flags_valid():
    assert _compose_flags(["IGNORECASE", "MULTILINE"]) == re.IGNORECASE | re.MULTILINE


def test_compose_flags_invalid():
    with pytest.raises(ValueError, match="desconocido"):
        _compose_flags(["INVALID_FLAG"])


def test_compose_flags_empty():
    assert _compose_flags([]) == 0


def test_make_regex_valid():
    cond = {"type": "REGEX", "field": "f", "pattern": "p"}
    matcher = make_regex(cond)
    assert isinstance(matcher, RegexMatcher)


def test_make_regex_missing_field_pattern():
    with pytest.raises(ValueError, match="obligatorios"):
        make_regex({"type": "REGEX"})


def test_make_regex_invalid_mode():
    with pytest.raises(ValueError, match="mode debe ser"):
        make_regex({"type": "REGEX", "field": "f", "pattern": "p", "mode": "invalid"})


def test_make_regex_invalid_coerce():
    with pytest.raises(ValueError, match="coerce inválido"):
        make_regex({"type": "REGEX", "field": "f", "pattern": "p", "coerce": "invalid"})


def test_make_regex_invalid_max_len():
    with pytest.raises(ValueError, match="max_len debe ser int > 0"):
        make_regex({"type": "REGEX", "field": "f", "pattern": "p", "max_len": 0})


def test_make_regex_timeout_without_regex_module(monkeypatch):
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.matchers.regex.HAS_REGEX", False)
    with pytest.raises(ValueError, match="requiere el módulo 'regex'"):
        make_regex({"type": "REGEX", "field": "f", "pattern": "p", "engine_timeout_ms": 100})


def test_make_regex_invalid_timeout():
    with pytest.raises(ValueError, match="engine_timeout_ms debe ser int > 0"):
        make_regex({"type": "REGEX", "field": "f", "pattern": "p", "engine_timeout_ms": 0})


def test_regex_module_not_found(monkeypatch):
    # Force the import of 'regex' to fail
    monkeypatch.setitem(sys.modules, "regex", None)

    # Unregister the matcher to avoid duplicate registration error on reload
    from kp_gateway_selector.gateway_selector.matchers.base import MATCHER_FACTORIES
    monkeypatch.delitem(MATCHER_FACTORIES, ("REGEX", "v1"), raising=False)

    # Reload the module to trigger the try/except block
    import importlib
    import kp_gateway_selector.gateway_selector.matchers.regex as regex_module
    importlib.reload(regex_module)

    assert regex_module.HAS_REGEX is False
    assert regex_module.rx_mod is re

def test_make_regex_with_invalid_pattern():
    import kp_gateway_selector.gateway_selector.matchers.regex as regex_module
    with pytest.raises(regex_module.rx_mod.error):
        make_regex({"type": "REGEX", "field": "f", "pattern": "(["})


def test_regex_matcher_call_no_field():
    matcher = RegexMatcher("f", "p", "search", 0, None, None, None, re.compile("p"))
    assert matcher({}) is False


def test_regex_matcher_call_coerce_str():
    matcher = RegexMatcher("f", "p", "search", 0, "str", None, None, re.compile("p"))
    assert matcher({"f": "p"}) is True


def test_regex_matcher_call_coerce_lower_str():
    matcher = RegexMatcher("f", "p", "search", 0, "lower-str", None, None, re.compile("p"))
    assert matcher({"f": "P"}) is True


def test_regex_matcher_call_no_coerce_non_str():
    matcher = RegexMatcher("f", "p", "search", 0, None, None, None, re.compile("p"))
    assert matcher({"f": 123}) is False


def test_regex_matcher_call_max_len_exceeded():
    matcher = RegexMatcher("f", "p", "search", 0, None, 2, None, re.compile("p"))
    assert matcher({"f": "ppp"}) is False


def test_regex_matcher_call_modes():
    # search
    matcher = RegexMatcher("f", "p", "search", 0, None, None, None, re.compile("p"))
    assert matcher({"f": "apa"}) is True
    # match
    matcher = RegexMatcher("f", "p", "match", 0, None, None, None, re.compile("p"))
    assert matcher({"f": "paa"}) is True
    assert matcher({"f": "apa"}) is False
    # fullmatch
    matcher = RegexMatcher("f", "p", "fullmatch", 0, None, None, None, re.compile("p"))
    assert matcher({"f": "p"}) is True
    assert matcher({"f": "pa"}) is False


def test_regex_matcher_call_with_timeout(monkeypatch):
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.matchers.regex.HAS_REGEX", True)
    mock_rx_mod = Mock()
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.matchers.regex.rx_mod", mock_rx_mod)

    cond = {"type": "REGEX", "field": "f", "pattern": "p", "engine_timeout_ms": 100}
    matcher = make_regex(cond)
    matcher({"f": "p"})
    mock_rx_mod.compile().search.assert_called_with("p", timeout=0.1)


def test_regex_matcher_call_with_timeout_match(monkeypatch):
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.matchers.regex.HAS_REGEX", True)
    mock_rx_mod = Mock()
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.matchers.regex.rx_mod", mock_rx_mod)

    cond = {"type": "REGEX", "field": "f", "pattern": "p", "mode": "match", "engine_timeout_ms": 100}
    matcher = make_regex(cond)
    matcher({"f": "p"})
    mock_rx_mod.compile().match.assert_called_with("p", timeout=0.1)


def test_regex_matcher_call_with_timeout_fullmatch(monkeypatch):
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.matchers.regex.HAS_REGEX", True)
    mock_rx_mod = Mock()
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.matchers.regex.rx_mod", mock_rx_mod)

    cond = {"type": "REGEX", "field": "f", "pattern": "p", "mode": "fullmatch", "engine_timeout_ms": 100}
    matcher = make_regex(cond)
    matcher({"f": "p"})
    mock_rx_mod.compile().fullmatch.assert_called_with("p", timeout=0.1)

def test_regex_matcher_name_property():
    """
    Tests the name property of the RegexMatcher.
    """
    matcher = RegexMatcher("f", "p", "search", 0, None, None, None, re.compile("p"))
    assert matcher.name == "REGEX"

def test_regex_matcher_str_representation():
    """
    Tests the __str__ representation of the RegexMatcher.
    """
    matcher = RegexMatcher("f", "p", "search", re.IGNORECASE, "lower-str", 128, 100, re.compile("p"))
    expected_str = f"REGEX(field=f, pattern=p, mode=search, flags_value={re.IGNORECASE}, coerce=lower-str, max_len=128, engine_timeout_ms=100)"
    assert str(matcher) == expected_str