from __future__ import annotations
from typing import Protocol, Callable, Dict, Any

class Matcher(Protocol):
    def __call__(self, ctx: Dict[str, Any]) -> bool: ...
    @property
    def name(self) -> str: ...
    def __str__(self) -> str: ...

# (type, impl) -> factory(cond_json) -> Matcher
MATCHER_FACTORIES: dict[tuple[str, str], Callable[[dict], Matcher]] = {}

def register_matcher(type_: str, impl: str = "v1"):
    def deco(factory: Callable[[dict], Matcher]):
        key = (type_, impl)
        if key in MATCHER_FACTORIES:
            raise ValueError(f"Matcher duplicado: {key}")
        MATCHER_FACTORIES[key] = factory
        return factory
    return deco

def build_matcher(cond: dict) -> Matcher:
    t = cond["type"]
    impl = cond.get("impl", "v1")
    try:
        factory = MATCHER_FACTORIES[(t, impl)]
    except KeyError:
        raise KeyError(f"Matcher no registrado: {t}:{impl}")
    return factory(cond)  # valida y devuelve instancia inmutable