import json
from kp_gateway_selector.gateway_selector.dtos import (
    GatewaySelectorGatewayConfigDTO,
    GatewaySelectorRuleDTO,
    GatewaySelectorRuleSetDTO,
)

def test_gateway_selector_gateway_config_dto_to_json():
    """
    Tests the to_json method of GatewaySelectorGatewayConfigDTO.
    """
    dto = GatewaySelectorGatewayConfigDTO(
        id=1,
        name="test-gw",
        is_enabled=True,
        in_maintenance=False,
    )
    json_str = dto.to_json()
    data = json.loads(json_str)
    assert data == {
        "id": 1,
        "name": "test-gw",
        "is_enabled": True,
        "in_maintenance": False,
    }

def test_gateway_selector_rule_dto_to_json():
    """
    Tests the to_json method of GatewaySelectorRuleDTO.
    """
    dto = GatewaySelectorRuleDTO(
        id=1,
        rule_set_id=1,
        priority=1,
        name="test-rule",
        enabled=True,
        condition_type="VALUE_IN",
        condition_value=None,
        condition_json={"field": "api_user_id", "values": [1, 2, 3]},
        action={"route": "FIXED", "gateway": "test-gw"},
    )
    json_str = dto.to_json()
    data = json.loads(json_str)
    assert data == {
        "id": 1,
        "rule_set_id": 1,
        "priority": 1,
        "name": "test-rule",
        "enabled": True,
        "condition_type": "VALUE_IN",
        "condition_value": None,
        "condition_json": {"field": "api_user_id", "values": [1, 2, 3]},
        "action": {"route": "FIXED", "gateway": "test-gw"},
    }

def test_gateway_selector_rule_set_dto_to_json():
    """
    Tests the to_json method of GatewaySelectorRuleSetDTO.
    """
    dto = GatewaySelectorRuleSetDTO(
        id=1,
        name="test-ruleset",
        is_active=True,
        sticky_salt="salty",
        default_gateway="default-gw",
        version=1,
    )
    json_str = dto.to_json()
    data = json.loads(json_str)
    assert data == {
        "id": 1,
        "name": "test-ruleset",
        "is_active": True,
        "sticky_salt": "salty",
        "default_gateway": "default-gw",
        "version": 1,
    }