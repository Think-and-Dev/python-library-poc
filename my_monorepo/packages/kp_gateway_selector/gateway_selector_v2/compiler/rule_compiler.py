from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Callable, Optional, List

from gateway_selector_v2.matchers.base import Matcher, build_matcher
from gateway_selector_v2.matchers.debug import DebugWrap

# --- Constantes útiles (evitan ifs en runtime) ---

@dataclass(frozen=True)
class ConstTrue(Matcher):
    @property
    def name(self) -> str: return "CONST_TRUE"
    def __call__(self, ctx: Dict[str, Any]) -> bool: return True

@dataclass(frozen=True)
class ConstFalse(Matcher):
    @property
    def name(self) -> str: return "CONST_FALSE"
    def __call__(self, ctx: Dict[str, Any]) -> bool: return False

CONST_TRUE = ConstTrue()
CONST_FALSE = ConstFalse()

# --- Combinadores ---

@dataclass(frozen=True)
class All(Matcher):
    """AND con short-circuit."""
    children: Tuple[Matcher, ...]
    @property
    def name(self) -> str: return "ALL"
    def __call__(self, ctx: Dict[str, Any]) -> bool:
        for ch in self.children:
            if not ch(ctx):  # short-circuit
                return False
        return True

@dataclass(frozen=True)
class Any(Matcher):
    """OR con short-circuit."""
    children: Tuple[Matcher, ...]
    @property
    def name(self) -> str: return "ANY"
    def __call__(self, ctx: Dict[str, Any]) -> bool:
        for ch in self.children:
            if ch(ctx):  # short-circuit
                return True
        return False

@dataclass(frozen=True)
class NoneOf(Matcher):
    """Negación de ANY(children)."""
    child: Matcher
    @property
    def name(self) -> str: return "NONE"
    def __call__(self, ctx: Dict[str, Any]) -> bool:
        return not self.child(ctx)

# --- Helpers de compilación ---

def _ensure_list(node: Any, key: str) -> List[Any]:
    if not isinstance(node.get(key), list):
        raise ValueError(f"Composite '{key}' debe ser una lista.")
    return node[key]

def _flatten(kind: str, children: List[Matcher]) -> List[Matcher]:
    """
    Colapsa combinadores anidados del mismo tipo.
    """
    flat: List[Matcher] = []
    for ch in children:
        if kind == "all" and isinstance(ch, All):
            flat.extend(ch.children)
        elif kind == "any" and isinstance(ch, Any):
            flat.extend(ch.children)
        else:
            flat.append(ch)
    return flat

def _fold_constants_for_all(children: List[Matcher]) -> Matcher:
    # Eliminar True; si hay un False → False
    kept: List[Matcher] = []
    for ch in children:
        if ch is CONST_FALSE:
            return CONST_FALSE
        if ch is CONST_TRUE:
            continue
        kept.append(ch)
    if not kept:
        return CONST_TRUE
    if len(kept) == 1:
        return kept[0]
    return All(tuple(kept))

def _fold_constants_for_any(children: List[Matcher]) -> Matcher:
    # Eliminar False; si hay un True → True
    kept: List[Matcher] = []
    for ch in children:
        if ch is CONST_TRUE:
            return CONST_TRUE
        if ch is CONST_FALSE:
            continue
        kept.append(ch)
    if not kept:
        return CONST_FALSE
    if len(kept) == 1:
        return kept[0]
    return Any(tuple(kept))

# --- Compilador principal ---

def compile_predicate(tree: dict, *,
                      debug: bool = False,
                      path: str = "ROOT",
                      log: Optional[Callable[[str], None]] = None,
                      capture_ctx_keys: bool = False) -> Matcher:
    """
    Compila un árbol de condiciones (JSON) a un Matcher ejecutable.
    Soporta 'all', 'any' y 'none' con:
      - flattening (colapso de niveles del mismo tipo),
      - constant folding,
      - short-circuit en runtime.
    """
    if not isinstance(tree, dict) or not tree:
        raise ValueError("Nodo inválido: se esperaba objeto no vacío.")
    keys = [k for k in ("all","any","none") if k in tree]
    if len(keys) > 1:
        raise ValueError(f"[{path}] Nodo compuesto ambiguo: usa solo uno de {keys}.")

    # Caso compuesto
    if "all" in tree:
        raw_children = _ensure_list(tree, "all")
        children = [
            compile_predicate(c, debug=debug, path=f"{path}.ALL[{i}]", log=log,
                              capture_ctx_keys=capture_ctx_keys)
            for i, c in enumerate(raw_children)
        ]
        children = _flatten("all", children)
        node = _fold_constants_for_all(children)
        return DebugWrap(node, path, log, capture_ctx_keys) if debug else node
    if "any" in tree:
        raw_children = _ensure_list(tree, "any")
        children = [
            compile_predicate(c, debug=debug, path=f"{path}.ANY[{i}]", log=log,
                              capture_ctx_keys=capture_ctx_keys)
            for i, c in enumerate(raw_children)
        ]
        children = _flatten("any", children)
        node = _fold_constants_for_any(children)
        return DebugWrap(node, path, log, capture_ctx_keys) if debug else node

    if "none" in tree:
        raw_children = _ensure_list(tree, "none")  # valida que sea lista
        # none([]) = not any([]) = not False = True
        if not raw_children:
            node = CONST_TRUE
        else:
            # compilá los hijos como un ANY (aplica flatten/folding allí)
            any_node = compile_predicate({"any": raw_children},
                                        debug=debug,
                                        path=f"{path}.NONE.ANY",
                                        log=log,
                                        capture_ctx_keys=capture_ctx_keys)
            # doblado de constantes (más explícito)
            if any_node is CONST_TRUE:
                node = CONST_FALSE
            elif any_node is CONST_FALSE:
                node = CONST_TRUE
            else:
                node = NoneOf(any_node)

        return DebugWrap(node, path, log, capture_ctx_keys) if debug else node

    # Hoja: construir matcher concreto (VALUE_IN, REGEX, AMOUNT_RANGE, etc.)
    if not isinstance(tree, dict) or "type" not in tree:
        raise ValueError("Hoja inválida: se esperaba un objeto con 'type'.")
    node = build_matcher(tree)
    return DebugWrap(node, path, log, capture_ctx_keys) if debug else node