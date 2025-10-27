import pytest
from unittest.mock import AsyncMock
from kp_gateway_selector.gateway_selector.compiler.ruleset_compiler import (
    _validate_action,
    _filter_to_condition_json,
    compile_ruleset,
    Repo,
    CompiledRuleset,
)
from kp_gateway_selector.gateway_selector.dtos import GatewaySelectorGatewayConfigDTO, GatewaySelectorRuleDTO, GatewaySelectorRuleSetDTO


@pytest.fixture
def gateways_configs():
    return {
        "E2E": GatewaySelectorGatewayConfigDTO(id=1, name="E2E", is_enabled=True, in_maintenance=False),
        "CELCOIN": GatewaySelectorGatewayConfigDTO(id=2, name="CELCOIN", is_enabled=True, in_maintenance=False),
    }


class MockRepo(Repo):
    def __init__(self, ruleset, rules, gateways):
        self.get_ruleset_by_id = AsyncMock(return_value=ruleset)
        self.get_active_ruleset = AsyncMock(return_value=ruleset)
        self.get_rules_for_ruleset = AsyncMock(return_value=rules)
        self.get_gateways_map = AsyncMock(return_value=gateways)


@pytest.mark.anyio("asyncio")
async def test_compile_ruleset_happy_path(gateways_configs, monkeypatch):
    ruleset_dto = GatewaySelectorRuleSetDTO(id=1, name="test", is_active=True, sticky_salt="salt", default_gateway="E2E", version=1)
    rules_dto = [
        GatewaySelectorRuleDTO(id=1, rule_set_id=1, priority=1, name="rule1", enabled=True, condition_type="ADVANCED", condition_value=None, condition_json={"type": "CONST_TRUE"}, action={"route": "FIXED", "gateway": "E2E"})
    ]
    repo = MockRepo(ruleset_dto, rules_dto, gateways_configs)

    monkeypatch.setattr("kp_gateway_selector.gateway_selector.compiler.ruleset_compiler.compile_predicate", lambda *args, **kwargs: True)

    compiled = await compile_ruleset(repo)

    assert isinstance(compiled, CompiledRuleset)
    assert compiled.ruleset_id == 1
    assert len(compiled.rules) == 1
    assert compiled.default_gateway == "E2E"


@pytest.mark.anyio("asyncio")
async def test_compile_ruleset_id_not_found():
    repo = MockRepo(None, [], {})
    with pytest.raises(RuntimeError, match="No se encontró el ruleset con ID 999"):
        await compile_ruleset(repo, ruleset_id=999)


@pytest.mark.anyio("asyncio")
async def test_compile_no_active_ruleset():
    repo = MockRepo(None, [], {})
    with pytest.raises(RuntimeError, match="No hay rule_set activo"):
        await compile_ruleset(repo)


@pytest.mark.anyio("asyncio")
async def test_compile_no_gateways():
    ruleset_dto = GatewaySelectorRuleSetDTO(id=1, name="test", is_active=True, sticky_salt="salt", default_gateway="E2E", version=1)
    repo = MockRepo(ruleset_dto, [], None)
    with pytest.raises(RuntimeError, match="No hay gateways configurados"):
        await compile_ruleset(repo)


@pytest.mark.anyio("asyncio")
async def test_compile_rule_adv_no_json(gateways_configs):
    ruleset_dto = GatewaySelectorRuleSetDTO(id=1, name="test", is_active=True, sticky_salt="salt", default_gateway="E2E", version=1)
    rules_dto = [
        GatewaySelectorRuleDTO(id=1, rule_set_id=1, priority=1, name="rule1", enabled=True, condition_type="ADVANCED", condition_value=None, condition_json=None, action={"route": "FIXED", "gateway": "E2E"})
    ]
    repo = MockRepo(ruleset_dto, rules_dto, gateways_configs)
    with pytest.raises(ValueError, match="ADVANCED requiere condition_json"):
        await compile_ruleset(repo)


@pytest.mark.anyio("asyncio")
async def test_compile_rule_simple_no_value(gateways_configs):
    ruleset_dto = GatewaySelectorRuleSetDTO(id=1, name="test", is_active=True, sticky_salt="salt", default_gateway="E2E", version=1)
    rules_dto = [
        GatewaySelectorRuleDTO(id=1, rule_set_id=1, priority=1, name="rule1", enabled=True, condition_type="USER", condition_value=None, condition_json=None, action={"route": "FIXED", "gateway": "E2E"})
    ]
    repo = MockRepo(ruleset_dto, rules_dto, gateways_configs)
    with pytest.raises(ValueError, match="USER requiere condition_value"):
        await compile_ruleset(repo)


@pytest.mark.anyio("asyncio")
async def test_compile_rule_with_user_condition_value(gateways_configs, monkeypatch):
    """Test compiling a rule with USER condition_type and valid condition_value."""
    ruleset_dto = GatewaySelectorRuleSetDTO(id=1, name="test", is_active=True, sticky_salt="salt", default_gateway="E2E", version=1)
    rules_dto = [
        GatewaySelectorRuleDTO(id=1, rule_set_id=1, priority=1, name="rule1", enabled=True, condition_type="USER", condition_value="123", condition_json=None, action={"route": "FIXED", "gateway": "E2E"})
    ]
    repo = MockRepo(ruleset_dto, rules_dto, gateways_configs)

    # Mock compile_predicate to avoid needing full matcher implementation
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.compiler.ruleset_compiler.compile_predicate", lambda *args, **kwargs: True)

    compiled = await compile_ruleset(repo)

    assert isinstance(compiled, CompiledRuleset)
    assert compiled.ruleset_id == 1
    assert len(compiled.rules) == 1


@pytest.mark.anyio("asyncio")
async def test_compile_rule_with_pix_key_condition_value(gateways_configs, monkeypatch):
    """Test compiling a rule with PIX_KEY condition_type and valid condition_value."""
    ruleset_dto = GatewaySelectorRuleSetDTO(id=1, name="test", is_active=True, sticky_salt="salt", default_gateway="E2E", version=1)
    rules_dto = [
        GatewaySelectorRuleDTO(id=1, rule_set_id=1, priority=1, name="rule1", enabled=True, condition_type="PIX_KEY", condition_value="test_key", condition_json=None, action={"route": "FIXED", "gateway": "CELCOIN"})
    ]
    repo = MockRepo(ruleset_dto, rules_dto, gateways_configs)

    # Mock compile_predicate to avoid needing full matcher implementation
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.compiler.ruleset_compiler.compile_predicate", lambda *args, **kwargs: True)

    compiled = await compile_ruleset(repo)

    assert isinstance(compiled, CompiledRuleset)
    assert compiled.ruleset_id == 1
    assert len(compiled.rules) == 1


@pytest.mark.anyio("asyncio")
async def test_compile_invalid_default_gateway(gateways_configs):
    ruleset_dto = GatewaySelectorRuleSetDTO(id=1, name="test", is_active=True, sticky_salt="salt", default_gateway="UNKNOWN", version=1)
    repo = MockRepo(ruleset_dto, [], gateways_configs)
    with pytest.raises(ValueError, match="Default gateway desconocido: 'UNKNOWN'"):
        await compile_ruleset(repo)


@pytest.mark.anyio("asyncio")
async def test_compile_with_log(gateways_configs):
    ruleset_dto = GatewaySelectorRuleSetDTO(id=1, name="test", is_active=True, sticky_salt="salt", default_gateway="E2E", version=1)
    rules_dto = []
    repo = MockRepo(ruleset_dto, rules_dto, gateways_configs)
    log_mock = []
    def logger(msg):
        log_mock.append(msg)

    await compile_ruleset(repo, log=logger)
    assert len(log_mock) == 1
    assert "[ruleset] compiled" in log_mock[0]


def test_validate_action_invalid_route(gateways_configs):
    with pytest.raises(ValueError, match="action.route inválido"):
        _validate_action({"route": "INVALID"}, gateways_configs, path="test")


def test_validate_action_fixed_no_gateway(gateways_configs):
    with pytest.raises(ValueError, match="FIXED requiere 'gateway' string"):
        _validate_action({"route": "FIXED"}, gateways_configs, path="test")


def test_validate_action_fixed_unknown_gateway(gateways_configs):
    with pytest.raises(ValueError, match="FIXED gateway desconocido"):
        _validate_action({"route": "FIXED", "gateway": "UNKNOWN"}, gateways_configs, path="test")


def test_validate_action_fixed_ok(gateways_configs):
    _validate_action({"route": "FIXED", "gateway": "E2E"}, gateways_configs, path="test")


def test_validate_action_weighted_no_weights(gateways_configs):
    with pytest.raises(ValueError, match="WEIGHTED requiere 'weights' dict no vacío"):
        _validate_action({"route": "WEIGHTED"}, gateways_configs, path="test")


def test_validate_action_weighted_unknown_gateway(gateways_configs):
    with pytest.raises(ValueError, match="WEIGHTED gateway desconocido"):
        _validate_action({"route": "WEIGHTED", "weights": {"UNKNOWN": 100}}, gateways_configs, path="test")


def test_validate_action_weighted_invalid_weight(gateways_configs):
    with pytest.raises(ValueError, match="WEIGHTED porcentaje inválido"):
        _validate_action({"route": "WEIGHTED", "weights": {"E2E": "abc"}}, gateways_configs, path="test")


def test_validate_action_weighted_negative_weight(gateways_configs):
    with pytest.raises(ValueError, match="WEIGHTED porcentaje negativo"):
        _validate_action({"route": "WEIGHTED", "weights": {"E2E": -10}}, gateways_configs, path="test")


def test_validate_action_weighted_all_zero_weights(gateways_configs):
    with pytest.raises(ValueError, match="WEIGHTED requiere al menos un peso > 0"):
        _validate_action({"route": "WEIGHTED", "weights": {"E2E": 0, "CELCOIN": 0}}, gateways_configs, path="test")


def test_validate_action_weighted_ok(gateways_configs):
    _validate_action({"route": "WEIGHTED", "weights": {"E2E": 100, "CELCOIN": 0}}, gateways_configs, path="test")


def test_validate_action_deny_invalid_reason_code(gateways_configs):
    with pytest.raises(ValueError, match="DENY.reason_code debe ser string"):
        _validate_action({"route": "DENY", "reason_code": 123}, gateways_configs, path="test")


def test_validate_action_deny_ok(gateways_configs):
    _validate_action({"route": "DENY", "reason_code": "some_reason"}, gateways_configs, path="test")


def test_filter_to_condition_json_user_invalid():
    with pytest.raises(ValueError, match="USER requiere entero"):
        _filter_to_condition_json("USER", "abc", path="test")


def test_filter_to_condition_json_user_ok():
    cond = _filter_to_condition_json("USER", "123", path="test")
    assert cond == {"type": "VALUE_IN", "field": "api_user_id", "values": [123], "coerce": "int"}


def test_filter_to_condition_json_pix_key_ok():
    cond = _filter_to_condition_json("PIX_KEY", "some_key", path="test")
    assert cond == {"type": "VALUE_IN", "field": "pix_key", "values": ["some_key"], "coerce": "str"}


def test_filter_to_condition_json_pix_key_type_invalid():
    with pytest.raises(ValueError, match="PIX_KEY_TYPE inválido"):
        _filter_to_condition_json("PIX_KEY_TYPE", "INVALID", path="test")


def test_filter_to_condition_json_pix_key_type_ok(monkeypatch):
    monkeypatch.setattr("kp_gateway_selector.gateway_selector.compiler.ruleset_compiler.ALLOWED_PIX_TYPES", {"CPF"})
    cond = _filter_to_condition_json("PIX_KEY_TYPE", "CPF", path="test")
    assert cond == {"type": "VALUE_IN", "field": "pix_key_type", "values": ["CPF"]}


def test_filter_to_condition_json_advanced():
    with pytest.raises(AssertionError, match="No expandir ADVANCED aquí"):
        _filter_to_condition_json("ADVANCED", "", path="test")


def test_filter_to_condition_json_unknown():
    with pytest.raises(ValueError, match="filter_type desconocido"):
        _filter_to_condition_json("UNKNOWN", "", path="test")

@pytest.mark.anyio("asyncio")
async def test_repo_protocol_not_implemented():
    """
    Tests that the methods of the Repo protocol raise NotImplementedError.
    This is to satisfy coverage reports, but it's not a typical test
    as Protocols are not meant to be instantiated directly.
    """
    class DummyRepo(Repo):
        pass

    repo = DummyRepo()

    with pytest.raises(NotImplementedError):
        await repo.get_ruleset_by_id(1)

    with pytest.raises(NotImplementedError):
        await repo.get_active_ruleset()

    with pytest.raises(NotImplementedError):
        await repo.get_rules_for_ruleset(1)

    with pytest.raises(NotImplementedError):
        await repo.get_gateways_map()