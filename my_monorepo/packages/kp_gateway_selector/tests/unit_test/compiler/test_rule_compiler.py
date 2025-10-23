import pytest
from kp_gateway_selector.gateway_selector.compiler.rule_compiler import (
    compile_predicate,
    CONST_TRUE,
    CONST_FALSE,
    All,
    Any,
    NoneOf,
    DebugWrap,
)
from kp_gateway_selector.gateway_selector.matchers.base import Matcher, build_matcher


class MockMatcher(Matcher):
    def __init__(self, result: bool):
        self._result = result

    def __call__(self, ctx):
        return self._result

    @property
    def name(self) -> str:
        return f"MockMatcher({self._result})"


@pytest.fixture
def mock_build_matcher(monkeypatch):
    def _build_matcher(tree: dict) -> Matcher:
        t = tree.get("type")
        if t == "mock_true":
            return MockMatcher(True)
        if t == "mock_false":
            return MockMatcher(False)
        if t == "CONST_TRUE":
            return CONST_TRUE
        if t == "CONST_FALSE":
            return CONST_FALSE
        # fallback to real builder for anything else
        return build_matcher(tree)

    monkeypatch.setattr(
        "kp_gateway_selector.gateway_selector.compiler.rule_compiler.build_matcher",
        _build_matcher,
        raising=True,
    )


def test_compile_invalid_node_types():
    with pytest.raises(ValueError, match="Nodo inválido: se esperaba objeto no vacío."):
        compile_predicate(None)
    with pytest.raises(ValueError, match="Nodo inválido: se esperaba objeto no vacío."):
        compile_predicate({})
    with pytest.raises(ValueError, match="Nodo inválido: se esperaba objeto no vacío."):
        compile_predicate([])  # type: ignore[arg-type]


def test_compile_ambiguous_composite_node():
    with pytest.raises(ValueError, match="Nodo compuesto ambiguo"):
        compile_predicate({"all": [], "any": []})


def test_compile_composite_with_non_list():
    with pytest.raises(ValueError, match="Composite 'all' debe ser una lista."):
        compile_predicate({"all": "not-a-list"})


def test_compile_invalid_leaf_node():
    with pytest.raises(ValueError, match="Hoja inválida: se esperaba un objeto con 'type'."):
        compile_predicate({"foo": "bar"})


def test_compile_none_with_empty_list_is_true(mock_build_matcher):
    rule = {"none": []}
    matcher = compile_predicate(rule)
    assert matcher is CONST_TRUE


def test_compile_none_with_const_true_child_is_false(mock_build_matcher):
    rule = {"none": [{"type": "CONST_TRUE"}]}
    matcher = compile_predicate(rule)
    assert matcher is CONST_FALSE


def test_compile_none_with_const_false_child_is_true(mock_build_matcher):
    rule = {"none": [{"type": "CONST_FALSE"}]}
    matcher = compile_predicate(rule)
    assert matcher is CONST_TRUE


def test_compile_none_with_regular_child(mock_build_matcher):
    rule = {"none": [{"type": "mock_true"}]}
    matcher = compile_predicate(rule)
    assert isinstance(matcher, NoneOf)
    assert isinstance(matcher.child, MockMatcher)


def test_compile_debug_mode_wraps_matcher(mock_build_matcher):
    rule = {"type": "mock_true"}
    matcher = compile_predicate(rule, debug=True)
    assert isinstance(matcher, DebugWrap)
    assert isinstance(matcher.inner, MockMatcher)


def test_compile_all_with_empty_list_is_true(mock_build_matcher):
    rule = {"all": []}
    matcher = compile_predicate(rule)
    assert matcher is CONST_TRUE


def test_compile_all_with_one_child(mock_build_matcher):
    rule = {"all": [{"type": "mock_true"}]}
    matcher = compile_predicate(rule)
    assert isinstance(matcher, MockMatcher)


def test_compile_all_with_multiple_children(mock_build_matcher):
    rule = {"all": [{"type": "mock_true"}, {"type": "mock_false"}]}
    matcher = compile_predicate(rule)
    assert isinstance(matcher, All)
    assert len(matcher.children) == 2


def test_compile_all_with_flattening(mock_build_matcher):
    rule = {"all": [{"all": [{"type": "mock_true"}, {"type": "mock_false"}]}]}
    matcher = compile_predicate(rule)
    assert isinstance(matcher, All)
    assert len(matcher.children) == 2


def test_compile_all_with_const_true_is_optimized(mock_build_matcher):
    rule = {"all": [{"type": "CONST_TRUE"}, {"type": "mock_true"}]}
    matcher = compile_predicate(rule)
    assert isinstance(matcher, MockMatcher)


def test_compile_all_with_const_false_is_const_false(mock_build_matcher):
    rule = {"all": [{"type": "CONST_FALSE"}, {"type": "mock_true"}]}
    matcher = compile_predicate(rule)
    assert matcher is CONST_FALSE


def test_compile_any_with_empty_list_is_false(mock_build_matcher):
    rule = {"any": []}
    matcher = compile_predicate(rule)
    assert matcher is CONST_FALSE


def test_compile_any_with_one_child(mock_build_matcher):
    rule = {"any": [{"type": "mock_true"}]}
    matcher = compile_predicate(rule)
    assert isinstance(matcher, MockMatcher)


def test_compile_any_with_multiple_children(mock_build_matcher):
    rule = {"any": [{"type": "mock_true"}, {"type": "mock_false"}]}
    matcher = compile_predicate(rule)
    assert isinstance(matcher, Any)
    assert len(matcher.children) == 2


def test_compile_any_with_flattening(mock_build_matcher):
    rule = {"any": [{"any": [{"type": "mock_true"}, {"type": "mock_false"}]}]}
    matcher = compile_predicate(rule)
    assert isinstance(matcher, Any)
    assert len(matcher.children) == 2


def test_compile_any_with_const_false_is_optimized(mock_build_matcher):
    rule = {"any": [{"type": "CONST_FALSE"}, {"type": "mock_true"}]}
    matcher = compile_predicate(rule)
    assert isinstance(matcher, MockMatcher)


def test_compile_any_with_const_true_is_const_true(mock_build_matcher):
    rule = {"any": [{"type": "CONST_TRUE"}, {"type": "mock_true"}]}
    matcher = compile_predicate(rule)
    assert matcher is CONST_TRUE
