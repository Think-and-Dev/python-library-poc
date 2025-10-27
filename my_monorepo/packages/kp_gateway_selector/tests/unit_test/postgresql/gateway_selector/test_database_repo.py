import pytest
from unittest.mock import MagicMock
from sqlalchemy.orm import Session
from kp_gateway_selector.postgresql.gateway_selector.database_repo import DatabaseRepo, WritableDatabaseRepo
from kp_gateway_selector.postgresql.gateway_selector.models import GatewaySelectorGatewayConfig, GatewaySelectorRule, GatewaySelectorRuleSet
from kp_gateway_selector.gateway_selector.dtos import GatewaySelectorRuleSetDTO, GatewaySelectorRuleDTO, GatewaySelectorGatewayConfigDTO

@pytest.fixture
def mock_db_session():
    """Fixture for a mock SQLAlchemy session."""
    return MagicMock(spec=Session)

@pytest.fixture
def database_repo(mock_db_session):
    """Fixture for WritableDatabaseRepo instance."""
    return WritableDatabaseRepo(mock_db_session)


def test_database_repo_init(mock_db_session):
    """Test that DatabaseRepo can be instantiated directly."""
    repo = DatabaseRepo(mock_db_session)
    assert repo.db == mock_db_session

@pytest.mark.anyio("asyncio")
async def test_get_ruleset_by_id_found(database_repo, mock_db_session):
    """Tests retrieving a ruleset by ID when it exists."""
    mock_ruleset = GatewaySelectorRuleSet(id=1, name="test_ruleset", is_active=True, sticky_salt="salt", version=1)
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_ruleset

    result = await database_repo.get_ruleset_by_id(1)

    assert result is not None
    assert isinstance(result, GatewaySelectorRuleSetDTO)
    assert result.id == 1
    mock_db_session.query.assert_called_once_with(GatewaySelectorRuleSet)
    mock_db_session.query.return_value.filter.assert_called_once()

@pytest.mark.anyio("asyncio")
async def test_get_ruleset_by_id_not_found(database_repo, mock_db_session):
    """Tests retrieving a ruleset by ID when it does not exist."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    result = await database_repo.get_ruleset_by_id(999)

    assert result is None
    mock_db_session.query.assert_called_once_with(GatewaySelectorRuleSet)
    mock_db_session.query.return_value.filter.assert_called_once()

@pytest.mark.anyio("asyncio")
async def test_get_active_ruleset_found(database_repo, mock_db_session):
    """Tests retrieving the active ruleset when it exists."""
    mock_ruleset = GatewaySelectorRuleSet(id=1, name="active_ruleset", is_active=True, sticky_salt="salt", version=1)
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_ruleset

    result = await database_repo.get_active_ruleset()

    assert result is not None
    assert isinstance(result, GatewaySelectorRuleSetDTO)
    assert result.is_active is True
    mock_db_session.query.assert_called_once_with(GatewaySelectorRuleSet)
    mock_db_session.query.return_value.filter.assert_called_once()

@pytest.mark.anyio("asyncio")
async def test_get_active_ruleset_not_found(database_repo, mock_db_session):
    """Tests retrieving the active ruleset when none is active."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    result = await database_repo.get_active_ruleset()

    assert result is None
    mock_db_session.query.assert_called_once_with(GatewaySelectorRuleSet)
    mock_db_session.query.return_value.filter.assert_called_once()

@pytest.mark.anyio("asyncio")
async def test_get_rules_for_ruleset(database_repo, mock_db_session):
    """Tests retrieving rules for a given ruleset ID."""
    mock_rule1 = GatewaySelectorRule(id=1, rule_set_id=1, priority=1, name="rule1", condition_type="ADVANCED", action={}, enabled=True)
    mock_rule2 = GatewaySelectorRule(id=2, rule_set_id=1, priority=2, name="rule2", condition_type="ADVANCED", action={}, enabled=True)
    mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_rule1, mock_rule2]

    result = await database_repo.get_rules_for_ruleset(1)

    assert len(result) == 2
    assert all(isinstance(r, GatewaySelectorRuleDTO) for r in result)
    assert result[0].id == 1
    assert result[1].id == 2
    mock_db_session.query.assert_called_once_with(GatewaySelectorRule)
    mock_db_session.query.return_value.filter.assert_called_once()
    mock_db_session.query.return_value.filter.return_value.order_by.assert_called_once()

@pytest.mark.anyio("asyncio")
async def test_get_rules_for_ruleset_no_rules(database_repo, mock_db_session):
    """Tests retrieving rules for a ruleset with no associated rules."""
    mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

    result = await database_repo.get_rules_for_ruleset(1)

    assert len(result) == 0
    mock_db_session.query.assert_called_once_with(GatewaySelectorRule)
    mock_db_session.query.return_value.filter.assert_called_once()
    mock_db_session.query.return_value.filter.return_value.order_by.assert_called_once()

@pytest.mark.anyio("asyncio")
async def test_get_gateways_map(database_repo, mock_db_session):
    """Tests retrieving the map of gateway configurations."""
    mock_gw1 = GatewaySelectorGatewayConfig(id=1, name="gw1", is_enabled=True, in_maintenance=False)
    mock_gw2 = GatewaySelectorGatewayConfig(id=2, name="gw2", is_enabled=False, in_maintenance=False)
    mock_db_session.query.return_value.all.return_value = [mock_gw1, mock_gw2]

    result = await database_repo.get_gateways_map()

    assert len(result) == 2
    assert "gw1" in result
    assert "gw2" in result
    assert isinstance(result["gw1"], GatewaySelectorGatewayConfigDTO)
    assert result["gw1"].id == 1
    assert result["gw2"].id == 2
    mock_db_session.query.assert_called_once_with(GatewaySelectorGatewayConfig)
    mock_db_session.query.return_value.all.assert_called_once()

@pytest.mark.anyio("asyncio")
async def test_get_gateways_map_no_gateways(database_repo, mock_db_session):
    """Tests retrieving the map of gateway configurations when none exist."""
    mock_db_session.query.return_value.all.return_value = []

    result = await database_repo.get_gateways_map()

    assert len(result) == 0
    mock_db_session.query.assert_called_once_with(GatewaySelectorGatewayConfig)
    mock_db_session.query.return_value.all.assert_called_once()

# --- Tests for WritableDatabaseRepo helper methods ---

def test_create_gateway_config_new(database_repo, mock_db_session):
    """Tests creating a new gateway configuration."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = None
    mock_db_session.add.side_effect = lambda x: setattr(x, 'id', 1) # Simulate ID assignment

    gateway = database_repo.create_gateway_config(id=1, name="new_gw")

    assert gateway.name == "new_gw"
    assert gateway.is_enabled is True
    assert gateway.updated_by == "pytest"
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(gateway)

def test_create_gateway_config_existing(database_repo, mock_db_session):
    """Tests creating a gateway configuration that already exists."""
    existing_gateway = GatewaySelectorGatewayConfig(id=1, name="existing_gw")
    mock_db_session.query.return_value.filter.return_value.first.return_value = existing_gateway

    gateway = database_repo.create_gateway_config(id=1, name="existing_gw")

    assert gateway == existing_gateway
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()
    mock_db_session.refresh.assert_not_called()

def test_create_ruleset_new_active(database_repo, mock_db_session):
    """Tests creating a new active ruleset."""
    mock_db_session.query.return_value.filter.return_value.update.return_value = None
    mock_db_session.add.side_effect = lambda x: setattr(x, 'id', 1) # Simulate ID assignment

    ruleset = database_repo.create_ruleset(name="new_ruleset", is_active=True)

    assert ruleset.name == "new_ruleset"
    assert ruleset.is_active is True
    assert ruleset.created_by == "pytest"
    mock_db_session.query.return_value.filter.return_value.update.assert_called_once_with({"is_active": False})
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(ruleset)

def test_create_ruleset_new_inactive(database_repo, mock_db_session):
    """Tests creating a new inactive ruleset."""
    mock_db_session.query.return_value.filter.return_value.update.return_value = None
    mock_db_session.add.side_effect = lambda x: setattr(x, 'id', 1) # Simulate ID assignment

    ruleset = database_repo.create_ruleset(name="new_ruleset", is_active=False)

    assert ruleset.name == "new_ruleset"
    assert ruleset.is_active is False
    mock_db_session.query.return_value.filter.return_value.update.assert_not_called() # Should not update if not active
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(ruleset)

def test_create_rule(database_repo, mock_db_session):
    """Tests creating a new rule."""
    mock_db_session.add.side_effect = lambda x: setattr(x, 'id', 1) # Simulate ID assignment

    rule = database_repo.create_rule(
        rule_set_id=1,
        priority=1,
        name="new_rule",
        action={"route": "FIXED", "gateway": "gw1"},
        condition_type="ADVANCED",
        condition_json={"type": "CONST_TRUE"}
    )

    assert rule.name == "new_rule"
    assert rule.rule_set_id == 1
    assert rule.created_by == "pytest"
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(rule)
