import math
import time
from decimal import Decimal
from typing import Dict, Any, List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo

# Imports from the new gateway selector v2 implementation
from kp_gateway_selector.gateway_selector.selector import select_gateway
from kp_gateway_selector.gateway_selector.context import make_ctx
from kp_gateway_selector.gateway_selector.compiler.ruleset_compiler import CompiledRuleset, CompiledRule
from kp_gateway_selector.postgresql.gateway_selector.models import GatewaySelectorGatewayConfig
import pytest
from kp_gateway_selector.gateway_selector.compiler.rule_compiler import compile_predicate, ConstTrue, ConstFalse
import regex

from collections import Counter

# --- Helper function to build a ruleset snapshot ---

def _build_snapshot(
    rules: List[CompiledRule],
    gateways: Dict[str, GatewaySelectorGatewayConfig],
    default_gateway: Optional[str] = None,
) -> CompiledRuleset:
    """Creates a CompiledRuleset snapshot for tests."""
    return CompiledRuleset(
        ruleset_id=1,
        version=1,
        name="test-ruleset",
        sticky_salt="test-salt",
        rules=tuple(sorted(rules, key=lambda r: r.priority)),
        gateways=gateways,
        default_gateway=default_gateway,
        loaded_at_ms=int(time.time() * 1000),
        total_rules=len(rules),
    )


# --- Test Suite ---


class TestGatewaySelector:
    """
    Test suite for the core logic of the gateway selector v2.
    """

    def setup_method(self):
        """Set up common test data."""
        self.ctx = make_ctx(
            api_user_id=123,
            pix_key="test@example.com",
            pix_key_type="EMAIL",
            amount=Decimal("100.00"),
        )
        self.gateways = {
            "gateway_a": GatewaySelectorGatewayConfig(
                name="gateway_a", is_enabled=True, in_maintenance=False
            ),
            "gateway_b": GatewaySelectorGatewayConfig(
                name="gateway_b", is_enabled=True, in_maintenance=False
            ),
            "gateway_c": GatewaySelectorGatewayConfig(
                name="gateway_c", is_enabled=False, in_maintenance=False
            ),
        }

    def test_rule_priority_is_respected(self):
        """
        Tests that rules are evaluated in priority order and the first one that matches wins.
        """
        # Arrange
        rule_low_priority = CompiledRule(
            id=1,
            priority=10,
            enabled=True,
            name="low",
            predicate=ConstTrue(),
            action={"route": "FIXED", "gateway": "gateway_b"},
        )
        rule_high_priority = CompiledRule(
            id=2,
            priority=5,
            enabled=True,
            name="high",
            predicate=ConstTrue(),
            action={"route": "FIXED", "gateway": "gateway_a"},
        )
        snapshot = _build_snapshot(
            [rule_low_priority, rule_high_priority], self.gateways
        )

        # Act
        gateway, decision = select_gateway(self.ctx, snapshot)

        # Assert
        assert gateway is not None
        assert gateway.name == "gateway_a"
        assert decision.matched_rule_id == 2

    def test_default_gateway_is_used_if_no_rules_match(self):
        """
        Tests that if no rules match the context, the system returns the default gateway.
        """
        # Arrange
        rule = CompiledRule(
            id=1,
            priority=10,
            enabled=True,
            name="non-matching",
            predicate=ConstFalse(),
            action={"route": "FIXED", "gateway": "gateway_a"},
        )
        snapshot = _build_snapshot([rule], self.gateways, default_gateway="gateway_b")

        # Act
        gateway, decision = select_gateway(self.ctx, snapshot)

        # Assert
        assert gateway is not None
        assert gateway.name == "gateway_b"
        assert decision.reason == "fallback"

    def test_disabled_rules_are_ignored(self):
        """
        Tests that a rule with enabled=False is skipped, even if it has the highest priority.
        """
        # Arrange
        disabled_rule = CompiledRule(
            id=1,
            priority=1,
            enabled=False,
            name="disabled",
            predicate=ConstTrue(),
            action={"route": "FIXED", "gateway": "gateway_a"},
        )
        enabled_rule = CompiledRule(
            id=2,
            priority=5,
            enabled=True,
            name="enabled",
            predicate=ConstTrue(),
            action={"route": "FIXED", "gateway": "gateway_b"},
        )
        snapshot = _build_snapshot([disabled_rule, enabled_rule], self.gateways)

        # Act
        gateway, decision = select_gateway(self.ctx, snapshot)

        # Assert
        assert gateway is not None
        assert gateway.name == "gateway_b"
        assert decision.matched_rule_id == 2

    def test_no_gateway_if_no_rules_match_and_no_default(self):
        """
        Tests that if no rules match and there is no default gateway, None is returned.
        """
        # Arrange
        rule = CompiledRule(
            id=1,
            priority=10,
            enabled=True,
            name="non-matching",
            predicate=ConstFalse(),
            action={"route": "FIXED", "gateway": "gateway_a"},
        )
        # Build a snapshot with no default_gateway
        snapshot = _build_snapshot([rule], self.gateways, default_gateway=None)

        # Act
        gateway, decision = select_gateway(self.ctx, snapshot)

        # Assert
        assert gateway is None
        assert decision.reason == "no_available_gw"

    def test_reason_is_no_rule_if_ruleset_is_empty(self):
        """
        Tests that reason is 'no_rule' if the ruleset is empty and there is no default.
        """
        # Arrange
        # Build a snapshot with no rules and no default_gateway
        snapshot = _build_snapshot([], self.gateways, default_gateway=None)

        # Act
        gateway, decision = select_gateway(self.ctx, snapshot)

        # Assert
        assert gateway is None
        assert decision.reason == "no_rule"


class TestGatewaySelectorFilters:
    """
    Tests for the various filter conditions (matchers) of a rule.
    """

    def setup_method(self):
        self.gateways = {
            "main_gw": GatewaySelectorGatewayConfig(
                name="main_gw", is_enabled=True, in_maintenance=False
            ),
        }
        self.default_gw = "default_gw"
        self.gateways[self.default_gw] = GatewaySelectorGatewayConfig(
            name=self.default_gw, is_enabled=True, in_maintenance=False
        )

    def _get_rule(self, cond: Dict[str, Any]) -> CompiledRule:
        return CompiledRule(
            id=1,
            priority=1,
            enabled=True,
            name="test-rule",
            predicate=compile_predicate(cond),
            action={"route": "FIXED", "gateway": "main_gw"},
        )

    def test_filter_by_api_user_id(self):
        """Tests a rule that should only match for a specific api_user_id."""
        # Arrange
        rule = self._get_rule(
            {"type": "VALUE_IN", "field": "api_user_id", "values": [123, 456]}
        )
        snapshot = _build_snapshot([rule], self.gateways, self.default_gw)

        matching_ctx = make_ctx(api_user_id=123)
        non_matching_ctx = make_ctx(api_user_id=999)

        # Act
        gw_match, _ = select_gateway(matching_ctx, snapshot)
        gw_no_match, _ = select_gateway(non_matching_ctx, snapshot)

        # Assert
        assert gw_match.name == "main_gw"
        assert gw_no_match.name == self.default_gw

    def test_filter_value_in_coerced_field(self):
        """Tests a rule that matches if the value in a coerced field is in the list of values."""
        # Arrange
        rules = [self._get_rule(
            {"type": "VALUE_IN", "field": "api_user_id", "values": [123, 456], "coerce": "str"}
        ), self._get_rule(
            {"type": "VALUE_IN", "field": "api_user_id", "values": [234, 567], "coerce": "int"}
        ), self._get_rule(
            {"type": "VALUE_IN", "field": "pix_key", "values": ["test_not_lowered@eXamPle.com"], "coerce": "str"}
        ), self._get_rule(
            {"type": "VALUE_IN", "field": "pix_key", "values": ["lower@eXamPle.com"], "coerce": "lower-str"}
        )]
        snapshot = _build_snapshot(rules, self.gateways, self.default_gw)

        matching_ctxs = [make_ctx(api_user_id="123"),
                         make_ctx(api_user_id=456),
                         make_ctx(api_user_id=234),
                         make_ctx(api_user_id="567"),
                         make_ctx(pix_key="test_not_lowered@eXamPle.com"),
                         make_ctx(pix_key="lowEr@eXAMPle.com")]
        non_matching_ctxs = [make_ctx(api_user_id="999"),
                             make_ctx(api_user_id=1243),
                             make_ctx(api_user_id="NAN"),
                             make_ctx(pix_key="test_not_lowered@example.com"),
                             make_ctx(pix_key="lowEr_invalid@example.com")]

        # Act & Assert
        for matching_ctx in matching_ctxs:
            gw_match, _ = select_gateway(matching_ctx, snapshot)
            assert gw_match.name == "main_gw"
        for non_matching_ctx in non_matching_ctxs:
            gw_no_match, _ = select_gateway(non_matching_ctx, snapshot)
            assert gw_no_match.name == self.default_gw

    def test_filter_value_in_invalid_coerced_field(self):
        """Tests a rule that matches if the value in a coerced field is in the list of values."""
        # Arrange
        cond = {"type": "VALUE_IN", "field": "api_user_id", "values": [123, 456], "coerce": "invalid"}
        with pytest.raises(ValueError, match="VALUE_IN: coerce inválido"):
            compile_predicate(cond)

    def test_filter_value_in_field_and_values_not_provided(self):
        """Tests a rule that matches if the value in a coerced field is in the list of values."""
        # Arrange
        cond = {"type": "VALUE_IN"}
        with pytest.raises(ValueError, match="VALUE_IN: field str y values list requeridos"):
            compile_predicate(cond)

    def test_filter_value_in_coerced_invalid_value(self):
        """Tests a rule that matches if the value in a coerced field is in the list of values."""
        # Arrange
        rule = self._get_rule(
            {"type": "VALUE_IN", "field": "api_user_id", "values": [123, 456], "coerce": "str"}
        )
        snapshot = _build_snapshot([rule], self.gateways, self.default_gw)

        matching_ctx = make_ctx(api_user_id="123")
        non_matching_ctx = make_ctx(api_user_id="999")

        # Act
        gw_match, _ = select_gateway(matching_ctx, snapshot)
        gw_no_match, _ = select_gateway(non_matching_ctx, snapshot)

        # Assert
        assert gw_match.name == "main_gw"
        assert gw_no_match.name == self.default_gw

    def test_filter_by_amount_threshold(self):
        """Tests a rule that matches if the amount is greater than a value."""
        # Arrange
        rule = self._get_rule(
            {
                "type": "AMOUNT_RANGE",
                "field": "amount",
                "min": "500",
                "min_inclusive": False,
            }
        )
        snapshot = _build_snapshot([rule], self.gateways, self.default_gw)

        matching_ctx = make_ctx(amount=Decimal("500.01"))
        non_matching_ctx = make_ctx(amount=Decimal("500.00"))

        # Act
        gw_match, _ = select_gateway(matching_ctx, snapshot)
        gw_no_match, _ = select_gateway(non_matching_ctx, snapshot)

        # Assert
        assert gw_match.name == "main_gw"
        assert gw_no_match.name == self.default_gw

    def test_composite_and_filter(self):
        """Tests a rule with a composite AND condition (all)."""
        # Arrange
        rule = self._get_rule(
            {
                "all": [
                    {"type": "VALUE_IN", "field": "api_user_id", "values": [123]},
                    {"type": "VALUE_IN", "field": "pix_key_type", "values": ["EMAIL"]},
                ]
            }
        )
        snapshot = _build_snapshot([rule], self.gateways, self.default_gw)

        # Act
        gw_match, _ = select_gateway(
            make_ctx(api_user_id=123, pix_key_type="EMAIL"), snapshot
        )
        gw_no_match1, _ = select_gateway(
            make_ctx(api_user_id=999, pix_key_type="EMAIL"), snapshot
        )
        gw_no_match2, _ = select_gateway(
            make_ctx(api_user_id=123, pix_key_type="CPF"), snapshot
        )

        # Assert
        assert gw_match.name == "main_gw"
        assert gw_no_match1.name == self.default_gw
        assert gw_no_match2.name == self.default_gw

    def test_composite_any_filter(self):
        """Tests a rule with a composite OR condition (any)."""
        # Arrange
        rule = self._get_rule(
            {
                "any": [
                    {"type": "VALUE_IN", "field": "api_user_id", "values": [123]},
                    {"type": "VALUE_IN", "field": "pix_key_type", "values": ["CPF"]},
                ]
            }
        )
        snapshot = _build_snapshot([rule], self.gateways, self.default_gw)

        # Act
        gw_match1, _ = select_gateway(
            make_ctx(api_user_id=123, pix_key_type="EMAIL"), snapshot
        )
        gw_match2, _ = select_gateway(
            make_ctx(api_user_id=999, pix_key_type="CPF"), snapshot
        )
        gw_no_match, _ = select_gateway(
            make_ctx(api_user_id=999, pix_key_type="EMAIL"), snapshot
        )

        # Assert
        assert gw_match1.name == "main_gw"
        assert gw_match2.name == "main_gw"
        assert gw_no_match.name == self.default_gw

    def test_composite_none_filter(self):
        """Tests a rule with a composite NOT condition (none)."""
        # Arrange
        # This rule matches if the user is NOT in the blocklist [999]
        rule = self._get_rule(
            {"none": [{"type": "VALUE_IN", "field": "api_user_id", "values": [999]}]}
        )
        snapshot = _build_snapshot([rule], self.gateways, self.default_gw)

        # Act
        gw_match, _ = select_gateway(make_ctx(api_user_id=123), snapshot)
        gw_no_match, _ = select_gateway(make_ctx(api_user_id=999), snapshot)

        # Assert
        assert gw_match.name == "main_gw"
        assert gw_no_match.name == self.default_gw

    def test_filter_by_regex(self):
        """Tests a rule that matches a regex pattern against a context field."""
        # Arrange
        # This rule matches emails ending in @private.com
        rule = self._get_rule(
            {"type": "REGEX", "field": "pix_key", "pattern": "@private\.com$"}
        )
        snapshot = _build_snapshot([rule], self.gateways, self.default_gw)

        # Act
        gw_match, _ = select_gateway(make_ctx(pix_key="user@private.com"), snapshot)
        gw_no_match, _ = select_gateway(
            make_ctx(pix_key="user@public.com"), snapshot
        )

        # Assert
        assert gw_match.name == "main_gw"
        assert gw_no_match.name == self.default_gw

    def test_filter_by_time_window(self):
        """Tests a rule that matches based on the time of day."""
        # Arrange
        # This rule is active between 09:00 and 18:00 in Sao Paulo time.
        rule = self._get_rule(
            {
                "type": "TIME_WINDOW",
                "tz": "America/Sao_Paulo",
                "start": "09:00",
                "end": "18:00",
            }
        )
        snapshot = _build_snapshot([rule], self.gateways, self.default_gw)

        tz = ZoneInfo("America/Sao_Paulo")

        # Act
        # Time inside the window
        gw_match, _ = select_gateway(
            make_ctx(now=datetime(2023, 1, 1, 10, 30, tzinfo=tz)), snapshot
        )
        # Time outside the window
        gw_no_match, _ = select_gateway(
            make_ctx(now=datetime(2023, 1, 1, 20, 0, tzinfo=tz)), snapshot
        )

        # Assert
        assert gw_match.name == "main_gw"
        assert gw_no_match.name == self.default_gw


class TestGatewaySelectorActions:
    """Tests for the various action types of a rule."""

    def setup_method(self):
        self.ctx = make_ctx(api_user_id=123)
        self.gateways = {
            "gateway_a": GatewaySelectorGatewayConfig(
                name="gateway_a", is_enabled=True, in_maintenance=False
            ),
            "gateway_b": GatewaySelectorGatewayConfig(
                name="gateway_b", is_enabled=True, in_maintenance=False
            ),
        }

    def test_action_fixed(self):
        """Tests a simple FIXED action."""
        # Arrange
        rule = CompiledRule(
            id=1,
            priority=1,
            enabled=True,
            name="fixed",
            predicate=ConstTrue(),
            action={"route": "FIXED", "gateway": "gateway_a"},
        )
        snapshot = _build_snapshot([rule], self.gateways)

        # Act
        gateway, _ = select_gateway(self.ctx, snapshot)

        # Assert
        assert gateway.name == "gateway_a"

    def test_action_weighted(self, mocker):
        """Tests the WEIGHTED action for traffic distribution."""
        # Arrange
        mocker.patch(
            "kp_gateway_selector.gateway_selector.selector._sticky_hash_bucket", return_value=79
        )
        action = {"route": "WEIGHTED", "weights": {"gateway_a": 80, "gateway_b": 20}}
        rule = CompiledRule(
            id=1,
            priority=1,
            enabled=True,
            name="weighted",
            predicate=ConstTrue(),
            action=action,
        )
        snapshot = _build_snapshot([rule], self.gateways)

        # Act
        gateway, _ = select_gateway(self.ctx, snapshot)

        # Assert
        assert gateway.name == "gateway_a"

    @pytest.mark.parametrize("weights", [
        {"gateway_a": 0, "gateway_b": 100},
        {"gateway_a": 10, "gateway_b": 90},
        {"gateway_a": 20, "gateway_b": 80},
        {"gateway_a": 30, "gateway_b": 70},
        {"gateway_a": 40, "gateway_b": 60},
        {"gateway_a": 50, "gateway_b": 50},
        {"gateway_a": 60, "gateway_b": 40},
        {"gateway_a": 70, "gateway_b": 30},
        {"gateway_a": 80, "gateway_b": 20},
        {"gateway_a": 90, "gateway_b": 10},
        {"gateway_a": 100, "gateway_b": 0}
    ])
    def test_weighted_distribution(self, weights):
        """
        Multiples tests con un ruleset WEIGHTED, en 10k requests
        la proporción debe estar dentro de 5 sigma puntos porcentuales.
        """
        action = {"route": "WEIGHTED", "weights": weights}
        rule = CompiledRule(id=1, priority=1, enabled=True, name="weighted", predicate=ConstTrue(), action=action)
        snapshot = _build_snapshot([rule], self.gateways)
        N = 10_000
        ctr = Counter()

        for i in range(N):
            ctx = {"api_user_id": i}  # cambia valor para distribuir sticky
            gw, decision = select_gateway(ctx, snapshot)
            assert gw is not None, decision
            ctr[gw.name] += 1

        ratio = ctr["gateway_a"] / N
        p_a = weights["gateway_a"] / 100
        sigma = math.sqrt(p_a * (1-p_a) / N)  # desviación estándar
        margin = 5*sigma

        if p_a in (0, 1):
            assert ratio == p_a
        else:
            lowerLimit = (p_a - margin )
            upperLimit = (p_a + margin)
            assert lowerLimit <= ratio <= upperLimit, f"Distribución fuera de rango: {ratio:.3f}"

    def test_action_deny(self):
        """Tests the DENY action, which should block the request."""
        # Arrange
        rule = CompiledRule(
            id=1,
            priority=1,
            enabled=True,
            name="deny",
            predicate=ConstTrue(),
            action={"route": "DENY", "reason_code": "test_deny"},
        )
        snapshot = _build_snapshot([rule], self.gateways)

        # Act
        gateway, decision = select_gateway(self.ctx, snapshot)

        # Assert
        assert gateway is None
        assert decision.reason == "denied"
        assert decision.matched_rule_id == 1

    def test_stickiness_by_user_id(self, mocker):
        """Tests that the same user always gets the same gateway from a WEIGHTED rule."""
        # Arrange
        def mock_hash(key: str, seed: str) -> int:
            if "user123" in key:
                return 25  # -> gateway_a
            if "user456" in key:
                return 90  # -> gateway_b
            return 50

        mocker.patch(
            "kp_gateway_selector.gateway_selector.selector._sticky_hash_bucket",
            side_effect=mock_hash,
        )
        action = {
            "route": "WEIGHTED",
            "weights": {"gateway_a": 80, "gateway_b": 20},
            "sticky_by": "api_user_id",
        }
        rule = CompiledRule(
            id=1,
            priority=1,
            enabled=True,
            name="sticky",
            predicate=ConstTrue(),
            action=action,
        )
        snapshot = _build_snapshot([rule], self.gateways)

        # Act
        gw1, _ = select_gateway(make_ctx(api_user_id="user123"), snapshot)
        gw2, _ = select_gateway(make_ctx(api_user_id="user456"), snapshot)
        gw3, _ = select_gateway(make_ctx(api_user_id="user123"), snapshot)

        # Assert
        assert gw1.name == "gateway_a"
        assert gw2.name == "gateway_b"
        assert gw3.name == "gateway_a"  # Same as first call

    def test_stickiness_gracefully_handles_missing_key(self, mocker):
        """
        Tests that stickiness falls back gracefully if the sticky_by key is not in the context.
        """
        # Arrange
        # We don't need to mock the hash function here, just ensure it doesn't crash.
        action = {
            "route": "WEIGHTED",
            "weights": {"gateway_a": 100},
            "sticky_by": "a_missing_key",
        }
        rule = CompiledRule(
            id=1,
            priority=1,
            enabled=True,
            name="missing_sticky_key",
            predicate=ConstTrue(),
            action=action,
        )
        snapshot = _build_snapshot([rule], self.gateways)

        # Act
        # The context is self.ctx, which does not have "a_missing_key"
        gateway, decision = select_gateway(self.ctx, snapshot)

        # Assert
        # The main point is that it didn't crash and returned a valid gateway.
        assert gateway is not None
        assert gateway.name == "gateway_a"

    def test_stickiness_by_pix_key(self, mocker):
        """Tests that the same pix_key always gets the same gateway from a WEIGHTED rule."""
        # Arrange
        def mock_hash(key: str, seed: str) -> int:
            if "key1@test.com" in key:
                return 15  # -> gateway_a
            if "key2@test.com" in key:
                return 85  # -> gateway_b
            return 50

        mocker.patch(
            "kp_gateway_selector.gateway_selector.selector._sticky_hash_bucket",
            side_effect=mock_hash,
        )
        action = {
            "route": "WEIGHTED",
            "weights": {"gateway_a": 70, "gateway_b": 30},
            "sticky_by": "pix_key",
        }
        rule = CompiledRule(
            id=1,
            priority=1,
            enabled=True,
            name="sticky_pix_key",
            predicate=ConstTrue(),
            action=action,
        )
        snapshot = _build_snapshot([rule], self.gateways)

        # Act
        gw1, _ = select_gateway(make_ctx(pix_key="key1@test.com"), snapshot)
        gw2, _ = select_gateway(make_ctx(pix_key="key2@test.com"), snapshot)
        gw3, _ = select_gateway(make_ctx(pix_key="key1@test.com"), snapshot)

        # Assert
        assert gw1.name == "gateway_a"
        assert gw2.name == "gateway_b"
        assert gw3.name == "gateway_a"  # Same as first call

    def test_action_weighted_with_one_gateway_in_maintenance(self, mocker):
        """Tests that weighted traffic is correctly redistributed if a gateway is in maintenance."""
        # Arrange
        mocker.patch(
            "kp_gateway_selector.gateway_selector.selector._sticky_hash_bucket", return_value=10
        )

        gateways_with_maintenance = {
            "gateway_a": GatewaySelectorGatewayConfig(
                name="gateway_a", is_enabled=True, in_maintenance=True
            ),
            "gateway_b": GatewaySelectorGatewayConfig(
                name="gateway_b", is_enabled=True, in_maintenance=False
            ),
        }
        action = {"route": "WEIGHTED", "weights": {"gateway_a": 50, "gateway_b": 50}}
        rule = CompiledRule(
            id=1,
            priority=1,
            enabled=True,
            name="maintenance-test",
            predicate=ConstTrue(),
            action=action,
        )
        snapshot = _build_snapshot([rule], gateways_with_maintenance)

        # Act
        gateway, _ = select_gateway(self.ctx, snapshot)

        # Assert
        assert gateway is not None
        assert gateway.name == "gateway_b"

    def test_action_fixed_with_unavailable_gateway(self):
        """Tests that the selector falls through a FIXED rule if the gateway is unavailable."""
        # Arrange
        gateways = {
            "gateway_a": GatewaySelectorGatewayConfig(
                name="gateway_a", is_enabled=False, in_maintenance=False
            ),  # Disabled
            "gateway_b": GatewaySelectorGatewayConfig(
                name="gateway_b", is_enabled=True, in_maintenance=False
            ),
        }

        # High priority rule points to the disabled gateway
        rule1 = CompiledRule(
            id=1,
            priority=5,
            enabled=True,
            name="fixed_unavailable",
            predicate=ConstTrue(),
            action={"route": "FIXED", "gateway": "gateway_a"},
        )

        # Lower priority rule points to the available gateway
        rule2 = CompiledRule(
            id=2,
            priority=10,
            enabled=True,
            name="fixed_available",
            predicate=ConstTrue(),
            action={"route": "FIXED", "gateway": "gateway_b"},
        )

        snapshot = _build_snapshot([rule1, rule2], gateways)

        # Act
        gateway, decision = select_gateway(self.ctx, snapshot)

        # Assert
        assert gateway is not None
        assert gateway.name == "gateway_b"
        assert decision.matched_rule_id == 2  # It should match the second rule

    def test_action_weighted_with_all_gateways_unavailable(self):
        """
        Tests that no gateway is chosen if all candidates in a WEIGHTED action are unavailable.
        """
        # Arrange
        gateways = {
            "gateway_a": GatewaySelectorGatewayConfig(
                name="gateway_a", is_enabled=False, in_maintenance=False
            ),
            "gateway_b": GatewaySelectorGatewayConfig(
                name="gateway_b", is_enabled=True, in_maintenance=True
            ),
        }
        action = {"route": "WEIGHTED", "weights": {"gateway_a": 50, "gateway_b": 50}}
        rule = CompiledRule(
            id=1,
            priority=1,
            enabled=True,
            name="all_unavailable",
            predicate=ConstTrue(),
            action=action,
        )

        # Note: We expect this to not find a gateway from the rule, and since there's
        # no default gateway configured in the snapshot, the final result should be None.
        snapshot = _build_snapshot([rule], gateways, default_gateway=None)

        # Act
        gateway, decision = select_gateway(self.ctx, snapshot)

        # Assert
        assert gateway is None
        # The reason should be 'no_available_gw' because a rule was matched, but its action
        # could not yield a usable gateway, and no other options (rules/default) were available.
        assert decision.reason == "no_available_gw"


class TestRuleCompilerValidation:
    """Tests the robustness of the rule compiler against invalid configurations."""

    def test_compile_predicate_with_invalid_range(self):
        """Tests that a rule with min > max is handled gracefully."""
        # Arrange: An invalid condition where min is greater than max
        invalid_condition = {
            "type": "AMOUNT_RANGE",
            "field": "amount",
            "min": "100",
            "max": "50",
        }

        # Act & Assert: The compiler should raise a ValueError for this invalid configuration.
        with pytest.raises(ValueError, match="AMOUNT_RANGE: max < min."):
            compile_predicate(invalid_condition)

    def test_compile_predicate_with_invalid_regex(self):
        """Tests that a rule with a broken regex pattern does not crash the compiler."""
        # Arrange: An invalid regex pattern
        invalid_condition = {"type": "REGEX", "field": "pix_key", "pattern": "(["}

        # Act & Assert: The compiler should raise an error for this invalid pattern.
        from kp_gateway_selector.gateway_selector.matchers.regex import HAS_REGEX
        import re
        error_type = regex.error if HAS_REGEX else re.error
        with pytest.raises(error_type):
            compile_predicate(invalid_condition)