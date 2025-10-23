from typing import List, Any, Dict, Optional
from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from cache.redis_base_cache import RedisBaseCache
from gateway_selector_v2.compiler.ruleset_compiler import Repo
from gateway_selector_v2.dtos import GatewaySelectorRuleSetDTO, GatewaySelectorRuleDTO, GatewaySelectorGatewayConfigDTO
from .models import GatewaySelectorGatewayConfig, GatewaySelectorRule, GatewaySelectorRuleSet

class DatabaseRepo(Repo):
    def __init__(self, db: Session):
        self.db = db

    async def get_ruleset_by_id(self, ruleset_id: int) -> Optional[GatewaySelectorRuleSetDTO]:
        result = self.db.query(GatewaySelectorRuleSet).filter(GatewaySelectorRuleSet.id == ruleset_id).first()
        return GatewaySelectorRuleSetDTO.model_validate(result) if result is not None else None

    async def get_active_ruleset(self) -> Optional[GatewaySelectorRuleSetDTO]:
        result = self.db.query(GatewaySelectorRuleSet).filter(GatewaySelectorRuleSet.is_active).first()        
        return GatewaySelectorRuleSetDTO.model_validate(result) if result is not None else None

    async def get_rules_for_ruleset(self, ruleset_id: int) -> List[GatewaySelectorRuleDTO]:
        result = self.db.query(GatewaySelectorRule).filter(GatewaySelectorRule.rule_set_id == ruleset_id).order_by(GatewaySelectorRule.priority).all()
        return [GatewaySelectorRuleDTO.model_validate(rule) for rule in result]

    async def get_gateways_map(self) -> Dict[str, GatewaySelectorGatewayConfigDTO]:
        gateways = self.db.query(GatewaySelectorGatewayConfig).all()
        return {gw.name: GatewaySelectorGatewayConfigDTO.model_validate(gw) for gw in gateways}

class DatabaseRepoWithCache(DatabaseRepo):
    RulesAdapter = TypeAdapter(List[GatewaySelectorRuleDTO])
    GatewaysMapAdapter = TypeAdapter(Dict[str, GatewaySelectorGatewayConfigDTO])
    def __init__(self, db: Session, ttl_gateways: int|None = None, ttl_ruleset: int|None = None, ttl_active_ruleset: int|None = None):
        super().__init__(db)
        self.cache_gateways = RedisBaseCache[str]()
        self.cache_ruleset = RedisBaseCache[str]()
        self.cache_active_ruleset = RedisBaseCache[str]()
        prefix = "gateway_selector_v2"
        self.cache_gateways._prefix = prefix
        self.cache_ruleset._prefix = prefix
        self.cache_active_ruleset._prefix = prefix
        self.ttl_gateways = ttl_gateways if ttl_gateways is not None else 300 # Default to 300 seconds
        self.ttl_ruleset = ttl_ruleset if ttl_ruleset is not None else 300 # Default to 300 seconds
        self.ttl_active_ruleset = ttl_active_ruleset if ttl_active_ruleset is not None else 300 # Default to 300 seconds

    async def get_active_ruleset(self) -> Optional[GatewaySelectorRuleSetDTO]:
        if self.cache_active_ruleset.get("active_ruleset") is None:
            active_ruleset = await super().get_active_ruleset()
            if active_ruleset is not None:
                self.cache_active_ruleset.set("active_ruleset", active_ruleset.model_dump_json(), ttl=self.ttl_active_ruleset)
            return active_ruleset
        cached_value = self.cache_active_ruleset.get("active_ruleset")
        return GatewaySelectorRuleSetDTO.model_validate_json(cached_value) if cached_value is not None else None

    async def get_rules_for_ruleset(self, ruleset_id: int) -> List[GatewaySelectorRuleDTO]:
        if self.cache_ruleset.get(f"rules_for_ruleset_{ruleset_id}") is None:
            rules_for_ruleset = await super().get_rules_for_ruleset(ruleset_id)
            self.cache_ruleset.set(f"rules_for_ruleset_{ruleset_id}", self.RulesAdapter.dump_json(rules_for_ruleset).decode("utf-8"), ttl=self.ttl_ruleset)
            return rules_for_ruleset
        cached_value = self.cache_ruleset.get(f"rules_for_ruleset_{ruleset_id}")
        return self.RulesAdapter.validate_json(cached_value) if cached_value is not None else []

    async def get_gateways_map(self) -> Dict[str, GatewaySelectorGatewayConfigDTO]:
        if self.cache_gateways.get("gateways_map") is None:
            gateways_map = await super().get_gateways_map()
            self.cache_gateways.set("gateways_map", self.GatewaysMapAdapter.dump_json(gateways_map).decode("utf-8"), ttl=self.ttl_gateways)
            return gateways_map
        cached_value = self.cache_gateways.get("gateways_map")
        return self.GatewaysMapAdapter.validate_json(cached_value) if cached_value is not None else {}

# --- Added write operations for testing purposes ---

class TestDatabaseRepo(DatabaseRepo):
    def __init__(self, db: Session):
        self.db = db

    def create_gateway_config(self, id: int, name: str, is_enabled: bool = True, in_maintenance: bool = False) -> GatewaySelectorGatewayConfig:
        """Creates a gateway configuration."""
        existing_gateway = self.db.query(GatewaySelectorGatewayConfig).filter(GatewaySelectorGatewayConfig.name == name).first()
        if existing_gateway:
            return existing_gateway

        new_gateway = GatewaySelectorGatewayConfig(
            id=id,
            name=name,
            is_enabled=is_enabled,
            in_maintenance=in_maintenance,
            updated_by="pytest",
        )
        self.db.add(new_gateway)
        self.db.commit()
        self.db.refresh(new_gateway)
        return new_gateway

    def create_ruleset(self, name: str, is_active: bool = True, sticky_salt: str = "test-salt", version: int = 1, default_gateway: Optional[str] = None) -> GatewaySelectorRuleSet:
        """Creates a new ruleset."""
        if is_active:
            self.db.query(GatewaySelectorRuleSet).filter(GatewaySelectorRuleSet.is_active == True).update({"is_active": False})

        new_ruleset = GatewaySelectorRuleSet(
            name=name,
            is_active=is_active,
            sticky_salt=sticky_salt,
            version=version,
            default_gateway=default_gateway,
            created_by="pytest"
        )
        self.db.add(new_ruleset)
        self.db.commit()
        self.db.refresh(new_ruleset)
        return new_ruleset

    def create_rule(self, rule_set_id: int, priority: int, name: str, action: Dict[str, Any], condition_type: str, condition_value: Optional[str] = None, condition_json: Optional[Dict[str, Any]] = None, enabled: bool = True) -> GatewaySelectorRule:
        """
        Creates a new rule in the database using condition_type, and either
        condition_value (for simple aliases) or condition_json (for advanced rules).
        """
        new_rule = GatewaySelectorRule(
            rule_set_id=rule_set_id,
            priority=priority,
            name=name,
            condition_type=condition_type,
            condition_json=condition_json,
            condition_value=condition_value,
            action=action,
            enabled=enabled,
            created_by="pytest",
        )
        self.db.add(new_rule)
        self.db.commit()
        self.db.refresh(new_rule)
        return new_rule
