
import pytest
from kp_gateway_selector.gateway_selector.matchers.base import (
    register_matcher,
    build_matcher,
    MATCHER_FACTORIES,
    Matcher,
)


class DummyMatcher(Matcher):
    def __call__(self, ctx):
        return True

    @property
    def name(self) -> str:
        return "dummy"


@register_matcher("DUMMY")
def dummy_factory(cond: dict) -> Matcher:
    return DummyMatcher()


def test_register_matcher():
    assert ("DUMMY", "v1") in MATCHER_FACTORIES
    assert MATCHER_FACTORIES[("DUMMY", "v1")] == dummy_factory


def test_register_duplicate_matcher():
    with pytest.raises(ValueError, match="Matcher duplicado"):
        @register_matcher("DUMMY")
        def dummy_factory_2(cond: dict) -> Matcher:
            return DummyMatcher()


def test_build_matcher_registered():
    matcher = build_matcher({"type": "DUMMY"})
    assert isinstance(matcher, DummyMatcher)


def test_build_matcher_unregistered():
    with pytest.raises(KeyError, match="Matcher no registrado"):
        build_matcher({"type": "UNREGISTERED"})