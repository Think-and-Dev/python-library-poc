from datetime import datetime
from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, String, Boolean, JSON, DateTime, UniqueConstraint
from database import Base

class GatewaySelectorRuleSet(Base):
    __tablename__ = "gateway_selector_rule_sets"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False, comment="Nombre del ruleset")
    is_active = Column(Boolean, default=False, nullable=False, comment="Flag para indicar si el ruleset está activo")
    sticky_salt = Column(String, comment="Sal para sticky session")
    default_gateway = Column(String, comment="Nombre del gateway por defecto")
    version = Column(Integer, default=0, nullable=False, comment="Versión del ruleset")
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="Fecha de creación del ruleset")
    created_by = Column(String, comment="Usuario que creó el ruleset")
    updated_at = Column(DateTime, comment="Fecha de actualización del ruleset")
    updated_by = Column(String, comment="Usuario que actualizó el ruleset")

    # índice parcial: sólo aplica a las filas donde is_active = true
    Index(
            "one_active_ruleset",
            is_active,
            unique=True,
            postgresql_where=(is_active == True)
    )
    __table_args__ = {
        'comment': "Tabla para almacenar los rulesets",
    }

class GatewaySelectorGatewayConfig(Base):
    __tablename__ = "gateway_selector_gateway_configs" # Ya hay una tabla 'gateways' en la base de datos, deberíamos usar esa o está bien crear una nueva? 
    id = Column(Integer, primary_key=True, autoincrement=False, comment="ID del gateway. Debe matchear con el value de la enumeración PaymentGateway")
    name = Column(String, unique=True, nullable=False, comment="Nombre del gateway")
    is_enabled = Column(Boolean, default=True, nullable=False, comment="Flag para indicar si el gateway está habilitado")
    in_maintenance = Column(Boolean, default=False, nullable=False, comment="Flag para indicar si el gateway está en mantenimiento")
    gateway_metadata = Column(JSON, comment="Metadatos del gateway")
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="Fecha de creación del gateway")
    updated_at = Column(DateTime, comment="Fecha de actualización del gateway")
    updated_by = Column(String, comment="Usuario que actualizó el gateway")

    __table_args__ = {
        'comment': "Tabla para almacenar la configuración de los gateways",
    }

class GatewaySelectorRule(Base):
    __tablename__ = "gateway_selector_rules"
    id = Column(Integer, primary_key=True)
    rule_set_id = Column(Integer, ForeignKey("gateway_selector_rule_sets.id"), nullable=False)
    priority = Column(Integer, nullable=False, comment="Prioridad de la regla")
    name = Column(String, comment="Nombre de la regla")
    enabled = Column(Boolean, default=True, nullable=False, comment="Flag para indicar si la regla está habilitada")

    condition_type  = Column(String, nullable=False, default="ADVANCED")
    condition_value = Column(String, nullable=True, comment="Valor de la condición en caso de que el tipo de condición no sea ADVANCED")
    condition_json  = Column(JSON, nullable=True, comment="Condición en caso de que el tipo de condición sea ADVANCED")

    action = Column(JSON, comment="Acción a ejecutar en caso de que la regla se cumpla")
    notes = Column(String, comment="Notas de la regla")
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="Fecha de creación de la regla")
    created_by = Column(String, comment="Usuario que creó la regla")
    updated_at = Column(DateTime, comment="Fecha de actualización de la regla")
    updated_by = Column(String, comment="Usuario que actualizó la regla")

    UniqueConstraint("rule_set_id", "priority"), # Forzamos a que no haya dos reglas con la misma prioridad en el mismo rule set
    Index("idx_rules_ruleset_priority", "rule_set_id", "priority"), # Índice parcial para mejor rendimiento en búsquedas
    Index("idx_rules_enabled", "rule_set_id", "enabled"), # Índice parcial para mejor rendimiento en búsquedas
    CheckConstraint("priority >= 0", name="ck_rules_priority_nonneg"), # Prioridad no puede ser negativa
    # CheckConstraint(
    #     """
    #     (condition_type = 'ADVANCED' AND condition_json IS NOT NULL AND condition_value IS NULL)
    #     OR
    #     (condition_type IN ('USER','PIX_KEY','PIX_KEY_TYPE') AND condition_value IS NOT NULL AND condition_json IS NULL)
    #     """,
    #     name="ck_rules_filter_consistency"
    # ) # Condición consistente entre condition_type y condition_value/condition_json
    __table_args__ = {
        'comment': "Tabla para almacenar las reglas",
    }

    @classmethod
    def create_with_condition_action(cls, condition: dict|None = None, action: dict|None = None, **kwargs):
        obj = cls(**kwargs)
        if condition is not None:
            obj.condition_json = condition
        if action is not None:
            obj.action = action
        return obj

