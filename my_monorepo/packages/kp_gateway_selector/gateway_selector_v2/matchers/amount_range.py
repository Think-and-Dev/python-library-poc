from dataclasses import dataclass
from typing import Dict, Any, Optional
from decimal import Decimal, InvalidOperation, getcontext

from .utils import _get_field

from .base import Matcher, register_matcher

getcontext().prec = 28  # seteamos la precisión a usar para comparaciones con decimales

def _to_decimal(val: Any) -> Optional[Decimal]:
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None

@dataclass(frozen=True)
class AmountRange(Matcher):
    """
    Matcher que valida que un monto numérico en el contexto (`ctx`) se encuentre dentro de un rango.

    Características:
    - Permite obtener el monto desde cualquier campo del `ctx` (ej. "amount", "payload.value").
    - Admite coerción del valor a Decimal a partir de int o string.
    - Soporta factor de escala para interpretar minor units (ej. centavos).
    - Permite definir límites inferior y/o superior (cada uno inclusivo o exclusivo).

    Ejemplos de configuración en JSON:
    ----------------------------------
    1) Monto en centavos, entre 10.00 y 1000.00 inclusive:
        {
          "type": "AMOUNT_RANGE",
          "field": "amount",
          "coerce": "int",
          "scale": 2,
          "min": "10.00",
          "max": "1000.00",
          "min_inclusive": true,
          "max_inclusive": true
        }

    2) Monto ya en decimal string, mayor a 500.00:
        {
          "type": "AMOUNT_RANGE",
          "field": "amount",
          "coerce": "decimal",
          "min": "500.00",
          "min_inclusive": false
        }
    """
    # Nombre del campo en el ctx desde el cual se obtiene el monto
    # (por defecto "amount", pero puede ser otro path).
    field: str

    # Cómo interpretar el valor extraído:
    # - "int": el valor viene como entero (ej. centavos), se aplicará scale.
    # - "decimal": el valor ya viene como string/Decimal representando un número con decimales.
    # - None: se asume Decimal por defecto.
    coerce: Optional[str]

    # Factor de escala si el valor es entero en minor units.
    # Ejemplo: 12345 con scale=2 → 123.45
    scale: int

    # Límite inferior permitido, como Decimal (o None si no hay límite).
    min_v: Optional[Decimal]

    # Límite superior permitido, como Decimal (o None si no hay límite).
    max_v: Optional[Decimal]

    # Si True, el límite inferior se considera inclusivo (>=).
    # Si False, exclusivo (>).
    min_inclusive: bool

    # Si True, el límite superior se considera inclusivo (<=).
    # Si False, exclusivo (<).
    max_inclusive: bool

    @property
    def name(self) -> str:
        return "AMOUNT_RANGE"

    def __call__(self, ctx: Dict[str, Any]) -> bool:
        raw = _get_field(ctx, self.field)
        if raw is None:
            return False

        # coerción
        if self.coerce == "int":
            try:
                iv = int(raw)
            except Exception:
                return False
            amt = Decimal(iv)
            if self.scale and self.scale > 0:
                amt = amt.scaleb(-self.scale)  # divide por 10**scale
        else:
            amt = _to_decimal(raw)
            if amt is None:
                return False

        # comparaciones
        if self.min_v is not None:
            if self.min_inclusive:
                if amt < self.min_v:
                    return False
            else:
                if amt <= self.min_v:
                    return False

        if self.max_v is not None:
            if self.max_inclusive:
                if amt > self.max_v:
                    return False
            else:
                if amt >= self.max_v:
                    return False

        return True

    def __str__(self) -> str:
        return f"AMOUNT_RANGE(field={self.field}, coerce={self.coerce}, scale={self.scale}, min_v={self.min_v}, max_v={self.max_v}, min_inclusive={self.min_inclusive}, max_inclusive={self.max_inclusive})"

@register_matcher("AMOUNT_RANGE", "v1")
def make_amount_range(cond: dict) -> Matcher:
    field = cond.get("field", "amount")
    if not isinstance(field, str):
        raise ValueError("AMOUNT_RANGE.field debe ser string.")

    coerce = cond.get("coerce", "decimal")
    if coerce not in ("int", "decimal", None):
        raise ValueError("AMOUNT_RANGE.coerce inválido.")

    scale = int(cond.get("scale", 0))
    if scale < 0:
        raise ValueError("AMOUNT_RANGE.scale debe ser >= 0.")

    min_raw = cond.get("min")
    max_raw = cond.get("max")
    min_v = _to_decimal(min_raw) if min_raw is not None else None
    max_v = _to_decimal(max_raw) if max_raw is not None else None
    if min_v is None and min_raw is not None:
        raise ValueError("AMOUNT_RANGE.min inválido.")
    if max_v is None and max_raw is not None:
        raise ValueError("AMOUNT_RANGE.max inválido.")
    if min_v is not None and max_v is not None and max_v < min_v:
        raise ValueError("AMOUNT_RANGE: max < min.")

    min_inclusive = bool(cond.get("min_inclusive", True))
    max_inclusive = bool(cond.get("max_inclusive", True))

    return AmountRange(
        field=field,
        coerce=coerce,
        scale=scale,
        min_v=min_v,
        max_v=max_v,
        min_inclusive=min_inclusive,
        max_inclusive=max_inclusive,
    )