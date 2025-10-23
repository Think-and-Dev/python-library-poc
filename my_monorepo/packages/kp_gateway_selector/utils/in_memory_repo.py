from typing import Optional, List, Dict, Any

from gateway_selector.compiler.ruleset_compiler import Repo
from gateway_selector.dtos import GatewaySelectorGatewayConfigDTO, GatewaySelectorRuleDTO, GatewaySelectorRuleSetDTO

class InMemoryRepo(Repo):
    """
    An in-memory repository for gateway selector rulesets, loaded from a JSON structure.
    This allows for validation and simulation without database interaction.
    """
    def __init__(self, data: Dict[str, Any]):
        # Provide default values for fields that might be missing in the JSON
        # but are required by the DTOs, mimicking DB defaults.
        gateway_data = data.get("gateways", [])
        for gw in gateway_data:
            gw.setdefault("in_maintenance", False)
        self._gateways = {gw['name']: GatewaySelectorGatewayConfigDTO(**gw) for gw in gateway_data}

        ruleset_data = data.get("ruleset", {})
        ruleset_data.setdefault("sticky_salt", "local-validation")
        ruleset_data.setdefault("version", 1)
        self._ruleset = GatewaySelectorRuleSetDTO(id=-1, **ruleset_data)

        rule_data = data.get("rules", [])
        for rule in rule_data:
            rule.setdefault("enabled", True)
            rule.setdefault("condition_json", None)
        self._rules = [GatewaySelectorRuleDTO(id=-1, rule_set_id=-1, **rule) for rule in rule_data]
        self._rules.sort(key=lambda r: r.priority)

    async def get_ruleset_by_id(self, ruleset_id: int) -> Optional[GatewaySelectorRuleSetDTO]:
        # For in-memory, we assume the loaded ruleset is the one we want to validate.
        # The ID doesn't matter in this context.
        return self._ruleset

    async def get_active_ruleset(self) -> Optional[GatewaySelectorRuleSetDTO]:
        # In a local context, the loaded ruleset is considered "active" for validation.
        return self._ruleset

    async def get_rules_for_ruleset(self, ruleset_id: int) -> List[GatewaySelectorRuleDTO]:
        # The ID is ignored as we only have one set of rules loaded.
        return self._rules

    async def get_gateways_map(self) -> Dict[str, GatewaySelectorGatewayConfigDTO]:
        return self._gateways
