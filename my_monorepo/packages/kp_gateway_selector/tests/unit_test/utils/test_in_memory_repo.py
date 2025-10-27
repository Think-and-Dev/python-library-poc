import pytest
from kp_gateway_selector.utils.in_memory_repo import InMemoryRepo
from kp_gateway_selector.gateway_selector.dtos import GatewaySelectorRuleSetDTO, GatewaySelectorGatewayConfigDTO

@pytest.fixture
def sample_data():
    return {
        "gateways": [
            {"name": "GW1", "id": 1, "is_enabled": True, "in_maintenance": False},
            {"name": "GW2", "id": 2, "is_enabled": True, "in_maintenance": True},
        ],
        "ruleset": {
            "name": "TestRuleset",
            "is_active": True,
            "version": 2,
            "default_gateway": "GW1",
            "sticky_salt": "local-validation"
        },
        "rules": [
            {
                "priority": 2,
                "name": "Rule2",
                "condition_type": "ADVANCED",
                "condition_value": "test-condition-2",
                "action": {"route": "FIXED", "gateway": "GW2"},
                "enabled": False,
                "condition_json": None
            },
            {
                "priority": 1,
                "name": "Rule1",
                "condition_type": "ADVANCED",
                "condition_value": "test-condition-1",
                "action": {"route": "FIXED", "gateway": "GW1"},
                "enabled": True,
                "condition_json": None
            },
        ],
    }

@pytest.fixture
def minimal_data():
    return {
        "gateways": [],
        "ruleset": {
            "name": "MinimalRuleset",
            "is_active": True,
            "default_gateway": "GW1"
        },
        "rules": []
    }

@pytest.fixture
def data_with_missing_gateway_fields():
    return {
        "gateways": [
            {"name": "GW3", "id": 3, "is_enabled": False},
            # in_maintenance will use default from InMemoryRepo
        ],
        "ruleset": {
            "name": "TestRuleset",
            "is_active": True,
            "default_gateway": "GW3"
        },
        "rules": []
    }

@pytest.fixture
def data_with_missing_ruleset_fields():
    return {
        "ruleset": {
            "name": "MinimalRuleset",
            "is_active": False,
            "default_gateway": "GW1"
            # sticky_salt and version will use defaults from InMemoryRepo
        },
        "gateways": [
            {"name": "GW1", "id": 1, "is_enabled": True, "in_maintenance": False}
        ],
        "rules": []
    }

@pytest.fixture
def data_with_missing_rule_fields():
    return {
        "ruleset": {
            "name": "TestRuleset",
            "is_active": True,
            "default_gateway": "GW1"
        },
        "gateways": [
            {"name": "GW1", "id": 1, "is_enabled": True, "in_maintenance": False}
        ],
        "rules": [
            {
                "priority": 1,
                "name": "Rule3",
                "condition_type": "ADVANCED",
                "condition_value": "test-condition-3",
                "action": {"route": "FIXED", "gateway": "GW1"}
                # enabled and condition_json will use defaults from InMemoryRepo
            },
        ]
    }

class TestInMemoryRepo:

    def test_init_complete_data(self, sample_data):
        repo = InMemoryRepo(sample_data)

        assert len(repo._gateways) == 2
        assert "GW1" in repo._gateways
        assert isinstance(repo._gateways["GW1"], GatewaySelectorGatewayConfigDTO)
        assert repo._gateways["GW1"].in_maintenance is False
        assert repo._gateways["GW2"].in_maintenance is True

        assert isinstance(repo._ruleset, GatewaySelectorRuleSetDTO)
        assert repo._ruleset.name == "TestRuleset"
        assert repo._ruleset.version == 2
        assert repo._ruleset.sticky_salt == "local-validation"

        assert len(repo._rules) == 2
        assert repo._rules[0].name == "Rule1"  # Sorted by priority
        assert repo._rules[0].enabled is True
        assert repo._rules[1].name == "Rule2"
        assert repo._rules[1].enabled is False

    def test_init_minimal_data(self, minimal_data):
        repo = InMemoryRepo(minimal_data)

        assert len(repo._gateways) == 0
        assert isinstance(repo._ruleset, GatewaySelectorRuleSetDTO)
        assert repo._ruleset.name == "MinimalRuleset"
        assert repo._ruleset.is_active is True
        assert repo._ruleset.sticky_salt == "local-validation"
        assert repo._ruleset.version == 1
        assert len(repo._rules) == 0

    def test_init_missing_gateway_fields(self, data_with_missing_gateway_fields):
        repo = InMemoryRepo(data_with_missing_gateway_fields)
        assert "GW3" in repo._gateways
        assert repo._gateways["GW3"].in_maintenance is False

    def test_init_missing_ruleset_fields(self, data_with_missing_ruleset_fields):
        repo = InMemoryRepo(data_with_missing_ruleset_fields)
        assert repo._ruleset.name == "MinimalRuleset"
        assert repo._ruleset.sticky_salt == "local-validation"
        assert repo._ruleset.version == 1

    def test_init_missing_rule_fields(self, data_with_missing_rule_fields):
        repo = InMemoryRepo(data_with_missing_rule_fields)
        assert len(repo._rules) == 1
        assert repo._rules[0].enabled is True
        assert repo._rules[0].condition_json is None

    @pytest.mark.anyio("asyncio")
    async def test_get_ruleset_by_id(self, sample_data):
        repo = InMemoryRepo(sample_data)
        ruleset = await repo.get_ruleset_by_id(123)  # ID is ignored
        assert ruleset == repo._ruleset

    @pytest.mark.anyio("asyncio")
    async def test_get_active_ruleset(self, sample_data):
        repo = InMemoryRepo(sample_data)
        ruleset = await repo.get_active_ruleset()
        assert ruleset == repo._ruleset

    @pytest.mark.anyio("asyncio")
    async def test_get_rules_for_ruleset(self, sample_data):
        repo = InMemoryRepo(sample_data)
        rules = await repo.get_rules_for_ruleset(456)  # ID is ignored
        assert rules == repo._rules

    @pytest.mark.anyio("asyncio")
    async def test_get_gateways_map(self, sample_data):
        repo = InMemoryRepo(sample_data)
        gateways = await repo.get_gateways_map()
        assert gateways == repo._gateways
