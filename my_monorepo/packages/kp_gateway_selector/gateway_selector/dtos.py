from typing import Optional
from pydantic import BaseModel, ConfigDict

class GatewaySelectorGatewayConfigDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore", frozen=True)
    id: int
    name: str
    is_enabled: bool
    in_maintenance: bool

    def to_json(self):
        return self.model_dump_json()

class GatewaySelectorRuleDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore", frozen=True)
    id: int
    rule_set_id: int
    priority: int
    name: Optional[str]
    enabled: bool
    condition_type: str
    condition_value: Optional[str]
    condition_json: Optional[dict]
    action: dict

    def to_json(self):
        return self.model_dump_json()

class GatewaySelectorRuleSetDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore", frozen=True)
    id: int
    name: str
    is_active: bool
    sticky_salt: Optional[str]
    default_gateway: Optional[str]
    version: int

    def to_json(self):
        return self.model_dump_json()