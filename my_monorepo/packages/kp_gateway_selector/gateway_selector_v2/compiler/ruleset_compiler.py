from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable, Protocol, Tuple

from utils.pix_key_types import PixKeyTypes
from gateway_selector_v2.dtos import GatewaySelectorGatewayConfigDTO, GatewaySelectorRuleDTO, GatewaySelectorRuleSetDTO

from .rule_compiler import compile_predicate, Matcher
from postgresql.gateway_selector_v2.models import GatewaySelectorGatewayConfig, GatewaySelectorRule, GatewaySelectorRuleSet

# --------------------------------------------------------------------
# Estructuras de datos del snapshot (inmutables para seguridad)
# --------------------------------------------------------------------

import logging
logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class CompiledRule:
    """
    Regla lista para ejecutar en el hot path.
    - predicate(ctx) -> bool ya compilado (con short-circuit).
    - action: JSON action "FIXED"/"WEIGHTED"/"DENY" (validada).
    """
    id: int
    priority: int
    enabled: bool
    name: Optional[str]
    predicate: Matcher
    action: Dict[str, Any]

@dataclass(frozen=True)
class CompiledRuleset:
    """
    Snapshot inmutable del ruleset activo.
    Usado por el selector en runtime y swappeado en hot-reload.
    """
    ruleset_id: int
    version: int
    name: str
    sticky_salt: Optional[str]

    # lista inmutable de Reglas ya compiladas, ordenadas por priority asc.
    rules: Tuple[CompiledRule, ...]
    # Gateways disponibles por nombre
    gateways: Dict[str, GatewaySelectorGatewayConfig]
    # Nombre del gateway por defecto (puede ser None si el motor maneja 503)
    default_gateway: Optional[str]

    # Telemetría/metadatos útiles
    loaded_at_ms: int
    total_rules: int

# --------------------------------------------------------------------
# Interfaz de repositorio (adaptala a tu ORM)
# --------------------------------------------------------------------

class Repo(Protocol):
    """Interfaz mínima que el compilador necesita. Implementala con SQLAlchemy."""
    async def get_ruleset_by_id(self, ruleset_id: int) -> Optional[GatewaySelectorRuleSetDTO]:
        """Devuelve {'id','name','version','sticky_salt','default_gateway', ...} o None."""
        raise NotImplementedError
    async def get_active_ruleset(self) -> Optional[GatewaySelectorRuleSetDTO]:
        """Devuelve {'id','name','version','sticky_salt','default_gateway', ...} o None."""
        raise NotImplementedError

    async def get_rules_for_ruleset(self, ruleset_id: int) -> List[GatewaySelectorRuleDTO]:
        """
        Devuelve lista de reglas ordenadas por priority asc, con campos:
        {'id','priority','enabled','name','condition','action'}.
        """
        raise NotImplementedError

    async def get_gateways_map(self) -> Dict[str, GatewaySelectorGatewayConfigDTO]:
        """Devuelve {'E2E': PaymentGateway(...), 'CELCOIN': ...}."""
        raise NotImplementedError

# TODO: Mover esto a un enum general, que se pueda usar desde advanced tmb, y desde el admin
ALLOWED_PIX_TYPES = {f.value for f in PixKeyTypes.__members__.values()}

def _filter_to_condition_json(filter_type: str, filter_value: str, *, path: str) -> dict:
    ft = filter_type.upper()
    if ft == "USER":
        try:
            uid = int(filter_value)
        except Exception:
            raise ValueError(f"[{path}] USER requiere entero, recibido: {filter_value!r}")
        return {"type": "VALUE_IN", "field": "api_user_id", "values": [uid], "coerce": "int"}

    if ft == "PIX_KEY":
        return {"type": "VALUE_IN", "field": "pix_key", "values": [filter_value], "coerce": "str"}

    if ft == "PIX_KEY_TYPE":
        t = str(filter_value).upper()
        if t not in ALLOWED_PIX_TYPES:
            raise ValueError(f"[{path}] PIX_KEY_TYPE inválido: {filter_value!r}")
        return {"type": "VALUE_IN", "field": "pix_key_type", "values": [t]}

    if ft == "ADVANCED":
        raise AssertionError("No expandir ADVANCED aquí")

    raise ValueError(f"[{path}] filter_type desconocido: {filter_type!r}")

# --------------------------------------------------------------------
# Compilador principal del ruleset
# --------------------------------------------------------------------

async def compile_ruleset(
    repo: Repo,
    *,
    ruleset_id: Optional[int] = None,
    debug: bool = False,
    log: Optional[Callable[[str], None]] = None,
    capture_ctx_keys: bool = False,
    validate_schema: bool = True,
) -> CompiledRuleset:
    """
    Carga, valida y compila el ruleset activo en un snapshot inmutable.

    Pasos:
    1) Lee ruleset activo + gateways + reglas (ordenadas)
    2) Valida esquema de cada regla (opcional)
    3) Compila condition -> predicate (con debug opcional)
    4) Valida acciones (FIXED/WEIGHTED/DENY) contra gateways
    5) Construye CompiledRuleset listo para swap atómico

    Args:
        repo: implementación de acceso a DB/servicios.
        ruleset_id: Opcional. Si se provee, compila el ruleset con ese ID en vez del activo.
        debug: si True, envuelve nodos con DebugWrap (trazas detalladas).
        log: función de log para DebugWrap.
        capture_ctx_keys: si True, DebugWrap imprime keys del ctx (no valores).
        validate_schema: corre validaciones de schema antes de compilar.

    Raises:
        RuntimeError/ValueError si la config es inválida.

    Returns:
        CompiledRuleset listo para usar.
    """
    import time
    t0 = time.perf_counter()

    if ruleset_id is not None:
        rs = await repo.get_ruleset_by_id(ruleset_id)
        if not rs:
            raise RuntimeError(f"No se encontró el ruleset con ID {ruleset_id}.")
    else:
        rs = await repo.get_active_ruleset()
        if not rs:
            raise RuntimeError("No hay rule_set activo.")

    gateways = await repo.get_gateways_map()
    if not gateways:
        raise RuntimeError("No hay gateways configurados.")

    rules_raw = await repo.get_rules_for_ruleset(rs.id)

    compiled_rules: List[CompiledRule] = []

    for r in rules_raw:
        rid = r.id
        try:
            cond:dict|None = None # condition json
            action = r.action

            # 1) TODO: Validación de schema
            # if validate_schema:
            #     validate_rule_schema(cond=cond, action=action, path=f"RULE[{rid}]")
            ftype = (r.condition_type or "ADVANCED").upper()
            fval  = r.condition_value
            fjson = r.condition_json
            rid   = r.id

            if ftype == "ADVANCED":
                if fjson is None:
                    raise ValueError(f"[RULE[{rid}]] ADVANCED requiere condition_json")
                cond = fjson
            else:
                if fval is None:
                    raise ValueError(f"[RULE[{rid}]] {ftype} requiere condition_value")
                cond = _filter_to_condition_json(ftype, fval, path=f"RULE[{rid}]")

            # 2) Compilación de la condición a Matcher
            predicate = compile_predicate(
                cond,
                debug=debug,
                path=f"RULE[{rid}]",
                log=log,
                capture_ctx_keys=capture_ctx_keys,
            )

            # 3) Validación de la acción contra gateways conocidos
            _validate_action(action, gateways, path=f"RULE[{rid}]")

            compiled_rules.append(
                CompiledRule(
                    id=rid,
                    priority=int(r.priority),
                    enabled=bool(r.enabled),
                    name=r.name,
                    predicate=predicate,
                    action=action,
                )
            )

        except Exception as ex:
            # Si una regla falla compilación/validación, abortamos la carga del set.
            # Alternativa: marcarla disabled y continuar, pero es más seguro fallar temprano.
            raise ValueError(f"[RULE[{rid}]] Error al compilar: {ex}") from ex

    # Orden defensivo por priority (aunque el repo ya la entregue ordenada)
    compiled_rules.sort(key=lambda x: x.priority)

    # 4) Default gateway (opcional)
    default_gw = rs.default_gateway
    if default_gw is not None and default_gw not in gateways:
        raise ValueError(f"Default gateway desconocido: '{default_gw}'")

    loaded_ms = ((time.perf_counter() - t0) * 1000.0)

    snapshot = CompiledRuleset(
        ruleset_id=rs.id,
        version=int(rs.version),
        name=rs.name,
        sticky_salt=rs.sticky_salt,
        rules=tuple(compiled_rules),
        gateways=gateways,
        default_gateway=default_gw,
        loaded_at_ms=loaded_ms,
        total_rules=len(compiled_rules),
    )

    if log:
        log(f"[ruleset] compiled id={snapshot.ruleset_id} version={snapshot.version} "
            f"rules={snapshot.total_rules} load_ms={snapshot.loaded_at_ms}")
    else:
        logger.info("ruleset compiled", extra={"ruleset_id": snapshot.ruleset_id, "version": snapshot.version, "total_rules": snapshot.total_rules, "loaded_at_ms": snapshot.loaded_at_ms})

    return snapshot

# --------------------------------------------------------------------
# Validaciones de acción (FIXED/WEIGHTED/DENY)
# --------------------------------------------------------------------

def _validate_action(action: Dict[str, Any], gateways_configs: Dict[str, GatewaySelectorGatewayConfig], *, path: str) -> None:
    """
    Valida que la acción exista y apunte a gateways conocidos/habilitables.
    - FIXED: 'gateway' requerido y conocido.
    - WEIGHTED: 'weights' dict con porcentajes >=0, al menos uno válido y todos conocidos.
    - DENY: opcional 'reason_code' string.
    """
    route = action.get("route")
    gateways = list(gateways_configs.keys())
    if route not in ("FIXED", "WEIGHTED", "DENY"):
        raise ValueError(f"[{path}] action.route inválido: {route}")

    if route == "FIXED":
        gw = action.get("gateway")
        if not isinstance(gw, str):
            raise ValueError(f"[{path}] FIXED requiere 'gateway' string.")
        if gw not in gateways:
            raise ValueError(f"[{path}] FIXED gateway desconocido: '{gw}'")
        return

    if route == "WEIGHTED":
        weights = action.get("weights")
        if not isinstance(weights, dict) or not weights:
            raise ValueError(f"[{path}] WEIGHTED requiere 'weights' dict no vacío.")
        total = 0
        any_valid = False
        for name, pct in weights.items():
            if name not in gateways:
                raise ValueError(f"[{path}] WEIGHTED gateway desconocido: '{name}'")
            try:
                iv = int(pct)
            except Exception:
                raise ValueError(f"[{path}] WEIGHTED porcentaje inválido para '{name}': {pct}")
            if iv < 0:
                raise ValueError(f"[{path}] WEIGHTED porcentaje negativo para '{name}': {iv}")
            total += iv
            any_valid = any_valid or (iv > 0)
        if not any_valid:
            raise ValueError(f"[{path}] WEIGHTED requiere al menos un peso > 0.")
        # (opcional) normalizar aquí y persistir en 'action' si querés
        # action["weights"] = normalize_weights(weights)
        return

    if route == "DENY":
        rc = action.get("reason_code")
        if rc is not None and not isinstance(rc, str):
            raise ValueError(f"[{path}] DENY.reason_code debe ser string.")
        return
