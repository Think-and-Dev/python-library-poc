import pytest
from kp_gateway_selector.gateway_selector.selector import (
    _normalize_weights,
    _sticky_hash_bucket,
    _pick_weighted,
    resolve_action,
    select_gateway,
)
from kp_gateway_selector.gateway_selector.compiler.ruleset_compiler import CompiledRule, CompiledRuleset
from kp_gateway_selector.postgresql.gateway_selector.models import GatewaySelectorGatewayConfig


@pytest.fixture
def gateways():
    return {
        "a": GatewaySelectorGatewayConfig(id=1, name="a", is_enabled=True, in_maintenance=False),
        "b": GatewaySelectorGatewayConfig(id=2, name="b", is_enabled=True, in_maintenance=False),
        "c": GatewaySelectorGatewayConfig(id=3, name="c", is_enabled=False, in_maintenance=False),
    }

@pytest.fixture
def ruleset(gateways):
    return CompiledRuleset(
        ruleset_id=1,
        version=1,
        name="test-ruleset",
        sticky_salt="salt",
        rules=(),
        gateways=gateways,
        default_gateway=None,
        loaded_at_ms=0,
        total_rules=0,
    )

def test_normalize_weights_empty():
    assert _normalize_weights({}) == {}

def test_normalize_weights_negative():
    assert _normalize_weights({"a": -10, "b": 20}) == {"b": 100}

def test_normalize_weights_all_zero():
    assert _normalize_weights({"a": 0, "b": 0}) == {}

def test_normalize_weights_sum_100():
    assert _normalize_weights({"a": 50, "b": 50}) == {"a": 50, "b": 50}

def test_normalize_weights_sum_not_100():
    assert _normalize_weights({"a": 10, "b": 10}) == {"a": 50, "b": 50}

def test_normalize_weights_rounding():
    assert _normalize_weights({"a": 1, "b": 2, "c": 1}) == {"a": 25, "b": 50, "c": 25}

def test_normalize_weights_three_thirds():
    assert _normalize_weights({"a": 33, "b": 33, "c": 33}) == {"a": 33, "b": 33, "c": 34}

def test_sticky_hash_bucket_deterministic():
    assert _sticky_hash_bucket("key", "seed") == _sticky_hash_bucket("key", "seed")

def test_sticky_hash_bucket_distribution():
    buckets = [_sticky_hash_bucket(str(i), "seed") for i in range(1000)]
    assert all(0 <= b <= 99 for b in buckets)
    # A very basic check for distribution, not a statistical test
    assert len(set(buckets)) > 50

def test_pick_weighted_no_candidates(gateways):
    assert _pick_weighted({}, gateways, sticky_by=None, ctx={}, seed="s") is None

def test_pick_weighted_no_available_candidates(gateways):
    assert _pick_weighted({"c": 100}, gateways, sticky_by=None, ctx={}, seed="s") is None

def test_pick_weighted_all_zero_weights(gateways):
    assert _pick_weighted({"a": 0, "b": 0}, gateways, sticky_by=None, ctx={}, seed="s") is None

def test_pick_weighted_sticky_by_key_present(gateways):
    gw1 = _pick_weighted({"a": 50, "b": 50}, gateways, sticky_by="user_id", ctx={"user_id": "123"}, seed="s")
    gw2 = _pick_weighted({"a": 50, "b": 50}, gateways, sticky_by="user_id", ctx={"user_id": "123"}, seed="s")
    assert gw1.name == gw2.name

def test_pick_weighted_sticky_by_key_not_present(gateways, monkeypatch):
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.selector._sticky_hash_bucket", lambda k, s: 10)
    gw1 = _pick_weighted({"a": 50, "b": 50}, gateways, sticky_by="user_id", ctx={}, seed="s")
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.selector._sticky_hash_bucket", lambda k, s: 90)
    gw2 = _pick_weighted({"a": 50, "b": 50}, gateways, sticky_by="user_id", ctx={}, seed="s")
    assert gw1.name == "a"
    assert gw2.name == "b"

def test_pick_weighted_no_sticky(gateways, monkeypatch):
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.selector._sticky_hash_bucket", lambda k, s: 10)
    gw1 = _pick_weighted({"a": 50, "b": 50}, gateways, sticky_by=None, ctx={}, seed="s")
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.selector._sticky_hash_bucket", lambda k, s: 90)
    gw2 = _pick_weighted({"a": 50, "b": 50}, gateways, sticky_by=None, ctx={}, seed="s")
    assert gw1.name == "a"
    assert gw2.name == "b"

def test_pick_weighted_bucketing(gateways, monkeypatch):
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.selector._sticky_hash_bucket", lambda k, s: 49)
    gw = _pick_weighted({"a": 50, "b": 50}, gateways, sticky_by="user_id", ctx={"user_id": "123"}, seed="s")
    assert gw.name == "a"

    monkeypatch.setattr("kp_gateway_selector.gateway_selector.selector._sticky_hash_bucket", lambda k, s: 50)
    gw = _pick_weighted({"a": 50, "b": 50}, gateways, sticky_by="user_id", ctx={"user_id": "123"}, seed="s")
    assert gw.name == "b"

def test_pick_weighted_unreachable_code(gateways, monkeypatch):
    # This test covers the safety net at the end of _pick_weighted,
    # which should not be reached in normal execution.
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.selector._normalize_weights", lambda w: {"a": 10, "b": 20})
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.selector._sticky_hash_bucket", lambda k, s: 40)
    gw = _pick_weighted({"a": 10, "b": 20}, gateways, sticky_by=None, ctx={}, seed="s")
    assert gw.name == "b" # 'b' is the last in sorted order

def test_resolve_action_deny(ruleset):
    rule = CompiledRule(id=1, priority=1, enabled=True, name="r", predicate=lambda ctx: True, action={"route": "DENY"})
    gw, reason = resolve_action(rule, ruleset, {})
    assert gw is None
    assert reason == "denied"

def test_resolve_action_fixed_available(ruleset):
    rule = CompiledRule(id=1, priority=1, enabled=True, name="r", predicate=lambda ctx: True, action={"route": "FIXED", "gateway": "a"})
    gw, reason = resolve_action(rule, ruleset, {})
    assert gw.name == "a"
    assert reason == "matched"

def test_resolve_action_fixed_unavailable(ruleset):
    rule = CompiledRule(id=1, priority=1, enabled=True, name="r", predicate=lambda ctx: True, action={"route": "FIXED", "gateway": "c"})
    gw, reason = resolve_action(rule, ruleset, {})
    assert gw is None
    assert reason == "fixed_unavailable"

def test_resolve_action_weighted_available(ruleset, monkeypatch):
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.selector._pick_weighted", lambda w, g, sticky_by, ctx, seed: g["a"])
    rule = CompiledRule(id=1, priority=1, enabled=True, name="r", predicate=lambda ctx: True, action={"route": "WEIGHTED", "weights": {"a": 100}})
    gw, reason = resolve_action(rule, ruleset, {})
    assert gw.name == "a"
    assert reason == "matched"

def test_resolve_action_weighted_unavailable(ruleset, monkeypatch):
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.selector._pick_weighted", lambda w, g, sticky_by, ctx, seed: None)
    rule = CompiledRule(id=1, priority=1, enabled=True, name="r", predicate=lambda ctx: True, action={"route": "WEIGHTED", "weights": {"a": 100}})
    gw, reason = resolve_action(rule, ruleset, {})
    assert gw is None
    assert reason == "weighted_unavailable"

def test_resolve_action_unknown_route(ruleset):
    rule = CompiledRule(id=1, priority=1, enabled=True, name="r", predicate=lambda ctx: True, action={"route": "UNKNOWN"})
    gw, reason = resolve_action(rule, ruleset, {})
    assert gw is None
    assert reason == "unknown_route"

@pytest.mark.anyio("asyncio")
async def test_gateway_selector_invalid_gateway_id(monkeypatch):
    """
    If a rule points to an unknown/invalid gateway name, selector should fall back to default.
    """
    gateways = {
        "a": GatewaySelectorGatewayConfig(id=1, name="a", is_enabled=True, in_maintenance=False),
        "b": GatewaySelectorGatewayConfig(id=2, name="b", is_enabled=True, in_maintenance=False),
    }
    rule = CompiledRule(
        id=1,
        priority=1,
        enabled=True,
        name="invalid-fixed",
        predicate=lambda ctx: True,
        action={"route": "FIXED", "gateway": "unknown"},  # not present in gateways
    )
    snapshot = CompiledRuleset(
        ruleset_id=1,
        version=1,
        name="rs",
        sticky_salt="s",
        rules=(rule,),
        gateways=gateways,
        default_gateway="a",
        loaded_at_ms=0,
        total_rules=1,
    )
    gw, decision = select_gateway({}, snapshot)
    assert gw is not None
    assert gw.name == "a"
    assert decision.reason == "fallback"

@pytest.mark.anyio("asyncio")
async def test_gateway_selector_no_gateway_found(monkeypatch):
    """
    If a matching rule cannot produce a usable gateway and there is no default, return None with reason no_available_gw.
    """
    gateways = {
        "c": GatewaySelectorGatewayConfig(id=3, name="c", is_enabled=False, in_maintenance=False),  # unavailable
    }
    rule = CompiledRule(
        id=1,
        priority=1,
        enabled=True,
        name="fixed-unavailable",
        predicate=lambda ctx: True,
        action={"route": "FIXED", "gateway": "c"},  # points to disabled gw
    )
    snapshot = CompiledRuleset(
        ruleset_id=1,
        version=1,
        name="rs",
        sticky_salt="s",
        rules=(rule,),
        gateways=gateways,
        default_gateway=None,
        loaded_at_ms=0,
        total_rules=1,
    )
    gw, decision = select_gateway({}, snapshot)
    assert gw is None
    assert decision.reason == "no_available_gw"
