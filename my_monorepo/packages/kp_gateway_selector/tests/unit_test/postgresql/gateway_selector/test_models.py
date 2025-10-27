import pytest
from kp_gateway_selector.postgresql.gateway_selector.models import (
    GatewaySelectorRule,
    GatewaySelectorRuleSet,
    GatewaySelectorGatewayConfig
)


class TestGatewaySelectorRule:
    """Tests for GatewaySelectorRule model."""

    def test_create_with_condition_action_all_params(self):
        """Test creating a rule with both condition and action."""
        condition = {"type": "CONST_TRUE"}
        action = {"route": "FIXED", "gateway": "GW1"}

        rule = GatewaySelectorRule.create_with_condition_action(
            condition=condition,
            action=action,
            rule_set_id=1,
            priority=1,
            name="test_rule",
            enabled=True,
            condition_type="ADVANCED"
        )

        assert rule.condition_json == condition
        assert rule.action == action
        assert rule.rule_set_id == 1
        assert rule.priority == 1
        assert rule.name == "test_rule"
        assert rule.enabled is True
        assert rule.condition_type == "ADVANCED"

    def test_create_with_condition_action_only_condition(self):
        """Test creating a rule with only condition."""
        condition = {"type": "REGEX", "field": "user_id", "pattern": "^test.*"}

        rule = GatewaySelectorRule.create_with_condition_action(
            condition=condition,
            rule_set_id=2,
            priority=5,
            name="condition_only_rule",
            condition_type="ADVANCED"
        )

        assert rule.condition_json == condition
        assert rule.action is None
        assert rule.rule_set_id == 2
        assert rule.priority == 5

    def test_create_with_condition_action_only_action(self):
        """Test creating a rule with only action."""
        action = {"route": "WEIGHTED", "weights": {"GW1": 50, "GW2": 50}}

        rule = GatewaySelectorRule.create_with_condition_action(
            action=action,
            rule_set_id=3,
            priority=10,
            name="action_only_rule",
            condition_type="ADVANCED"
        )

        assert rule.condition_json is None
        assert rule.action == action
        assert rule.rule_set_id == 3
        assert rule.priority == 10

    def test_create_with_condition_action_no_condition_no_action(self):
        """Test creating a rule without condition or action."""
        rule = GatewaySelectorRule.create_with_condition_action(
            rule_set_id=4,
            priority=15,
            name="minimal_rule",
            condition_type="ADVANCED"
        )

        assert rule.condition_json is None
        assert rule.action is None
        assert rule.rule_set_id == 4
        assert rule.priority == 15
        assert rule.name == "minimal_rule"

    def test_create_with_condition_action_none_values(self):
        """Test creating a rule with explicit None values for condition and action."""
        rule = GatewaySelectorRule.create_with_condition_action(
            condition=None,
            action=None,
            rule_set_id=5,
            priority=20,
            condition_type="ADVANCED"
        )

        assert rule.condition_json is None
        assert rule.action is None
        assert rule.rule_set_id == 5
        assert rule.priority == 20


class TestGatewaySelectorRuleSet:
    """Tests for GatewaySelectorRuleSet model."""

    def test_ruleset_instantiation(self):
        """Test basic instantiation of GatewaySelectorRuleSet."""
        ruleset = GatewaySelectorRuleSet(
            id=1,
            name="test_ruleset",
            is_active=True,
            sticky_salt="test-salt",
            default_gateway="GW1",
            version=1
        )

        assert ruleset.id == 1
        assert ruleset.name == "test_ruleset"
        assert ruleset.is_active is True
        assert ruleset.sticky_salt == "test-salt"
        assert ruleset.default_gateway == "GW1"
        assert ruleset.version == 1


class TestGatewaySelectorGatewayConfig:
    """Tests for GatewaySelectorGatewayConfig model."""

    def test_gateway_config_instantiation(self):
        """Test basic instantiation of GatewaySelectorGatewayConfig."""
        gateway = GatewaySelectorGatewayConfig(
            id=1,
            name="GW1",
            is_enabled=True,
            in_maintenance=False,
            gateway_metadata={"key": "value"}
        )

        assert gateway.id == 1
        assert gateway.name == "GW1"
        assert gateway.is_enabled is True
        assert gateway.in_maintenance is False
        assert gateway.gateway_metadata == {"key": "value"}

    def test_gateway_config_defaults(self):
        """Test default values for GatewaySelectorGatewayConfig."""
        gateway = GatewaySelectorGatewayConfig(
            id=2,
            name="GW2"
        )

        assert gateway.id == 2
        assert gateway.name == "GW2"
        # Note: defaults are set by SQLAlchemy when inserting to DB,
        # not on instantiation, so we just verify the object is created
