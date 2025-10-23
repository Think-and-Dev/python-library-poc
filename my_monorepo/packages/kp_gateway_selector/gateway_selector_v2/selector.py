# selector.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional
from hashlib import sha256
from uuid import uuid4

from gateway_selector_v2.compiler.ruleset_compiler import CompiledRuleset, CompiledRule
from gateway_selector_v2.context import GatewaySelectorCtx
from postgresql.gateway_selector_v2.models import GatewaySelectorGatewayConfig

# ---------------------------------------------------------
# Estructuras de salida (útiles para log/telemetría)
# ---------------------------------------------------------

@dataclass(frozen=True)
class Decision:
    matched_rule_id: Optional[int]
    route: Optional[str]
    gateway: Optional[str]
    reason: str  # "matched", "denied", "no_rule", "fallback", "no_available_gw"

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _gw_ok(gw: GatewaySelectorGatewayConfig) -> bool:
    return gw.is_enabled and not gw.in_maintenance

def _normalize_weights(weights: Dict[str, int]) -> Dict[str, int]:
    """Clampea negativos a 0, filtra 0s, y normaliza a suma 100 (si > 0)."""
    cleaned = {k: max(0, int(v)) for k, v in weights.items()}
    cleaned = {k: v for k, v in cleaned.items() if v > 0}
    total = sum(cleaned.values())
    if total == 0:
        return {}
    if total == 100:
        return cleaned
    # normalizar proporcionalmente a 100
    acc = 0
    out: Dict[str, int] = {}
    items = sorted(cleaned.items())  # orden determinístico
    for i, (k, v) in enumerate(items):
        if i == len(items) - 1:
            out[k] = 100 - acc
        else:
            pct = int(round(v * 100.0 / total))
            out[k] = pct
            acc += pct
    # puede quedar 99/101 por redondeo; ajustar último arriba.
    diff = 100 - sum(out.values())
    if diff:
        last = next(reversed(out))
        out[last] += diff
    return out

def _sticky_hash_bucket(key: str, seed: str) -> int:
    """Devuelve un número 0..99 estable para (key, seed)."""
    h = sha256((key + ":" + seed).encode("utf-8")).hexdigest()
    return int(h, 16) % 100

def _pick_weighted(
    weights: Dict[str, int],
    gateways: Dict[str, GatewaySelectorGatewayConfig],
    *,
    sticky_by: Optional[str],
    ctx: Dict[str, Any],
    seed: str,
) -> Optional[GatewaySelectorGatewayConfig]:
    """Elige un GW ponderado, con sticky opcional."""
    # filtrar por disponibilidad
    candidates = {k: v for k, v in weights.items() if k in gateways and _gw_ok(gateways[k])}
    if not candidates:
        return None
    norm = _normalize_weights(candidates)
    if not norm:
        return None

    # clave de sticky (si no hay, aleatorio estable por request)
    if sticky_by:
        key_val = ctx.get(sticky_by)
        # si no está ese campo en ctx, caemos a un UUID por request
        key = str(key_val) if key_val is not None else str(uuid4())
    else:
        key = str(uuid4())

    bucket = _sticky_hash_bucket(key, seed)  # 0..99

    cumulative = 0
    # orden determinístico
    for gw_name, pct in sorted(norm.items()):
        cumulative += pct
        if bucket < cumulative:
            return gateways[gw_name]
    # por seguridad (no debería pasar)
    last_name = next(reversed(sorted(norm)))
    return gateways[last_name]

# ---------------------------------------------------------
# Resolve action
# ---------------------------------------------------------

def resolve_action(
    rule: CompiledRule,
    snapshot: CompiledRuleset,
    ctx: Dict[str, Any],
) -> tuple[Optional[GatewaySelectorGatewayConfig], str]:
    """
    Devuelve (gateway, reason). Si la acción es DENY, (None, "denied").
    """
    action = rule.action
    route = action.get("route")

    # Seed para sticky: aisla entre rulesets y reglas
    seed = f"{snapshot.ruleset_id}:{snapshot.version}:{snapshot.sticky_salt or ''}:{rule.id}"

    if route == "DENY":
        return None, "denied"

    if route == "FIXED":
        gw_name = action.get("gateway")
        gw = snapshot.gateways.get(gw_name)
        if gw and _gw_ok(gw):
            return gw, "matched"
        return None, "fixed_unavailable"

    if route == "WEIGHTED":
        sticky_by = action.get("sticky_by")  # "api_user_id" | "pix_key" | ...
        weights = action.get("weights") or {}
        gw = _pick_weighted(weights, snapshot.gateways, sticky_by=sticky_by, ctx=ctx, seed=seed)
        if gw:
            return gw, "matched"
        return None, "weighted_unavailable"

    return None, "unknown_route"

# ---------------------------------------------------------
# Gateway selector (hot path)
# ---------------------------------------------------------

def select_gateway(
    ctx: GatewaySelectorCtx,
    snapshot: CompiledRuleset,
    *,
    allow_fallback: bool = True,
    on_decision: Optional[callable] = None,  # hook para logging/metrics
) -> tuple[Optional[GatewaySelectorGatewayConfig], Decision]:
    """
    Evalúa reglas compiladas y decide un gateway.
    Retorna (gateway | None, Decision).
    - Si DENY: gateway=None y reason="denied".
    - Si no matchea ninguna regla:
        - si hay default y está ok → fallback,
        - si no → None con reason="no_rule" o "no_available_gw".
    """
    # 1) evaluar reglas en orden
    for rule in snapshot.rules:
        if not rule.enabled:
            continue
        if rule.predicate(ctx):
            gw, reason = resolve_action(rule, snapshot, ctx)
            if reason == "denied":
                dec = Decision(rule.id, "DENY", None, "denied")
                if on_decision: on_decision(dec, ctx)
                return None, dec
            if gw:
                dec = Decision(rule.id, snapshot and rule.action.get("route"), gw.name, reason)
                if on_decision: on_decision(dec, ctx)
                return gw, dec
            # Si la acción no produjo gw (apagado/mantenimiento), seguimos probando
            # la siguiente regla; esto permite “fallback entre reglas”.

    # 2) fallback global (si corresponde)
    if allow_fallback and snapshot.default_gateway:
        gw = snapshot.gateways.get(snapshot.default_gateway)
        if gw and _gw_ok(gw):
            dec = Decision(None, None, gw.name, "fallback")
            if on_decision: on_decision(dec, ctx)
            return gw, dec

    # 3) sin regla y sin fallback disponible
    # distinguir entre “no hubo regla” vs “hubo pero no había gw disponible”
    reason = "no_rule"
    # heurística simple: si existía al menos una regla enabled → “no_available_gw”
    if any(r.enabled for r in snapshot.rules):
        reason = "no_available_gw"

    dec = Decision(None, None, None, reason)
    if on_decision: on_decision(dec, ctx)
    return None, dec
