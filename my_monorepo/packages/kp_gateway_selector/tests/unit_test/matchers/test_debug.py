import pytest
from unittest.mock import Mock
from kp_gateway_selector.gateway_selector.matchers.debug import DebugWrap
from kp_gateway_selector.gateway_selector.matchers.base import Matcher


class MockMatcher(Matcher):
    def __init__(self, result: bool):
        self._result = result

    def __call__(self, ctx):
        return self._result

    @property
    def name(self) -> str:
        return "mock"

    def __str__(self) -> str:
        return f"MockMatcher({self._result})"


def test_debug_wrap_calls_inner_matcher():
    inner = MockMatcher(True)
    wrapper = DebugWrap(inner, "path")
    assert wrapper({}) is True


def test_debug_wrap_with_log_function(monkeypatch):
    log_fn = Mock()
    inner = MockMatcher(False)
    wrapper = DebugWrap(inner, "path", log=log_fn, capture_ctx_keys=True)
    wrapper({"key": "value"})
    log_fn.assert_called_once()
    call_args = log_fn.call_args[0][0]
    assert "path=path" in call_args
    assert "result=False" in call_args
    assert "ctx_keys=['key']" in call_args


def test_debug_wrap_with_log_function_no_keys(monkeypatch):
    log_fn = Mock()
    inner = MockMatcher(True)
    wrapper = DebugWrap(inner, "path", log=log_fn, capture_ctx_keys=False)
    wrapper({"key": "value"})
    log_fn.assert_called_once()
    call_args = log_fn.call_args[0][0]
    assert "ctx_keys" not in call_args


def test_debug_wrap_with_default_logger(monkeypatch):
    mock_logger_debug = Mock()
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.matchers.debug.logger.debug", mock_logger_debug)
    inner = MockMatcher(True)
    wrapper = DebugWrap(inner, "path", capture_ctx_keys=True)
    wrapper({"key": "value"})
    mock_logger_debug.assert_called_once()
    extra = mock_logger_debug.call_args[1]["extra"]
    assert extra["path"] == "path"
    assert extra["result"] is True
    assert extra["ctx_keys"] == ["key"]


def test_debug_wrap_with_default_logger_no_keys(monkeypatch):
    mock_logger_debug = Mock()
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.matchers.debug.logger.debug", mock_logger_debug)
    inner = MockMatcher(False)
    wrapper = DebugWrap(inner, "path", capture_ctx_keys=False)
    wrapper({"key": "value"})
    mock_logger_debug.assert_called_once()
    extra = mock_logger_debug.call_args[1]["extra"]
    assert "ctx_keys" not in extra

def test_debug_wrap_name_property():
    """
    Tests the name property of the DebugWrap matcher.
    """
    inner = MockMatcher(True)
    wrapper = DebugWrap(inner, "path")
    assert wrapper.name == "DBG(mock)"