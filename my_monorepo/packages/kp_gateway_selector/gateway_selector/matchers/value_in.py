from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Optional

from .utils import _get_field
from .base import Matcher, register_matcher

@dataclass(frozen=True)
class ValueIn(Matcher):
    """
    Matcher genérico que valida si un valor del contexto (`ctx`) se encuentra
    dentro de una lista blanca (`values`).

    Características:
    - El campo a validar se indica mediante `field`, soportando paths anidados.
    - El valor extraído puede ser transformado con `coerce` antes de comparar.
    - La lista de valores válidos se precalcula como un `frozenset` para mejorar performance.

    Ejemplo de configuración (JSON):
    --------------------------------
    {
      "type": "VALUE_IN",
      "field": "api_user_id",
      "values": [101, 102, 103],
      "coerce": "int"
    }

    Ejemplo de uso:
    ---------------
    ctx = {"api_user_id": 101}
    → True (porque 101 ∈ {101,102,103})
    """

    # Campo del ctx del cual obtener el valor a validar
    field: str

    # Conjunto de valores permitidos (ya precompilados como frozenset para lookup O(1))
    values: FrozenSet[Any]

    # Cómo transformar el valor extraído antes de comparar:
    # - "int": lo convierte a int
    # - "str": lo convierte a string
    # - "lower-str": lo convierte a string en minúsculas
    # - None: no se transforma
    coerce: Optional[str] = None

    @property
    def name(self) -> str: return "VALUE_IN"

    def __call__(self, ctx: Dict[str, Any]) -> bool:
        v = _get_field(ctx, self.field)
        if v is None:
            return False
        if self.coerce == "int":
            try: v = int(v)
            except Exception: return False
        elif self.coerce == "str":
            v = str(v)
        elif self.coerce == "lower-str":
            v = str(v).lower()
        return v in self.values

    def __str__(self) -> str:
        return f"VALUE_IN(field={self.field}, values={self.values}, coerce={self.coerce})"

@register_matcher("VALUE_IN", "v1")
def make_value_in(cond: dict) -> Matcher:
    field = cond.get("field")
    values = cond.get("values", [])
    if not isinstance(field, str) or not isinstance(values, list):
        raise ValueError("VALUE_IN: field str y values list requeridos")
    coerce = cond.get("coerce")
    if coerce not in (None, "int", "str", "lower-str"):
        raise ValueError("VALUE_IN: coerce inválido")
    # Precoerción homogénea del set (para no convertir en cada request)
    def to_coerced(val):
        if coerce == "int": return int(val)
        if coerce == "str": return str(val)
        if coerce == "lower-str": return str(val).lower()
        return val
    canon = frozenset(to_coerced(x) for x in values)
    return ValueIn(field=field, values=canon, coerce=coerce)