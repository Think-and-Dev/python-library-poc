from dataclasses import dataclass
from typing import Dict, Any, Iterable, Optional

from .utils import _get_field
from .base import Matcher, register_matcher
import re

try:
    import regex as rx_mod  # opcional, mejor por timeout
    HAS_REGEX = True
except Exception:
    rx_mod = re
    HAS_REGEX = False

# map de flags válidos
_FLAG_MAP = {
    "IGNORECASE": re.IGNORECASE,
    "MULTILINE": re.MULTILINE,
    "DOTALL": re.DOTALL,
    "ASCII": re.ASCII,
    "VERBOSE": re.VERBOSE,
}

def _compose_flags(flags: Optional[Iterable[str]]) -> int:
    f = 0
    if not flags:
        return f
    for name in flags:
        if name not in _FLAG_MAP:
            raise ValueError(f"REGEX.flags desconocido: {name}")
        f |= _FLAG_MAP[name]
    return f

@dataclass(frozen=True)
class RegexMatcher(Matcher):
    """
    Matcher que valida si un campo del contexto (`ctx`) cumple con
    una expresión regular.

    Características:
    - Permite elegir el campo (`field`) y el modo de match (`search`, `match`, `fullmatch`).
    - Precompila la regex con los flags indicados para performance.
    - Admite coerción previa (`str`, `lower-str`) para normalizar el valor.
    - Permite limitar longitud máxima del string (`max_len`) para evitar ReDoS.
    - Opcionalmente (si se instala el paquete `regex`), permite timeout de ejecución.

    Ejemplo de configuración (JSON):
    --------------------------------
    {
      "type": "REGEX",
      "field": "pix_key",
      "pattern": "@kamipay\\.io$",
      "mode": "search",
      "flags": ["IGNORECASE"],
      "coerce": "str",
      "max_len": 256
    }

    Ejemplo de uso:
    ---------------
    ctx = {"pix_key": "mati@kamipay.io"}
    → True (matchea el patrón "@kamipay\\.io$")
    """

    # Nombre del campo en el ctx del cual obtener el valor a evaluar
    field: str

    # Patrón regex como string
    pattern: str

    # Modo de evaluación: "search" (default), "match" (desde inicio) o "fullmatch" (toda la cadena)
    mode: str

    # Flags combinados de re/regex (ej. IGNORECASE, MULTILINE)
    flags_value: int

    # Cómo normalizar el valor antes de aplicar la regex
    # - "str": convertir a string
    # - "lower-str": string en minúsculas
    # - None: no transformar
    coerce: Optional[str]

    # Longitud máxima del string permitido (None = sin límite)
    max_len: Optional[int]

    # Timeout en ms para ejecutar la regex (requiere módulo 'regex')
    engine_timeout_ms: Optional[int]

    # Objeto regex precompilado (re.Pattern o regex.Pattern)
    compiled: Any

    @property
    def name(self) -> str:
        return "REGEX"

    def __call__(self, ctx: Dict[str, Any]) -> bool:
        v = _get_field(ctx, self.field)
        if v is None:
            return False

        # coerción
        if self.coerce == "str":
            v = str(v)
        elif self.coerce == "lower-str":
            v = str(v).lower()
        elif not isinstance(v, str):
            return False

        # límite de longitud
        if self.max_len is not None and len(v) > self.max_len:
            # Quizás podríamos elegir truncar: v = v[:self.max_len]
            return False

        # ejecutar con modo/timeout si hay 'regex' disponible
        if HAS_REGEX and self.engine_timeout_ms:
            timeout = self.engine_timeout_ms / 1000.0
            if self.mode == "match":
                m = self.compiled.match(v, timeout=timeout)
            elif self.mode == "fullmatch":
                m = self.compiled.fullmatch(v, timeout=timeout)
            else:
                m = self.compiled.search(v, timeout=timeout)
        else:
            if self.mode == "match":
                m = self.compiled.match(v)
            elif self.mode == "fullmatch":
                # en 're' standard fullmatch puede faltar en versiones muy viejas:
                m = self.compiled.fullmatch(v) if hasattr(self.compiled, "fullmatch") \
                    else (self.compiled.match(v) if self.compiled.match(v) and self.compiled.match(v).group(0) == v else None)
            else:
                m = self.compiled.search(v)

        return bool(m)

    def __str__(self) -> str:
        return f"REGEX(field={self.field}, pattern={self.pattern}, mode={self.mode}, flags_value={self.flags_value}, coerce={self.coerce}, max_len={self.max_len}, engine_timeout_ms={self.engine_timeout_ms})"

@register_matcher("REGEX", "v1")
def make_regex(cond: dict) -> Matcher:
    field = cond.get("field")
    pattern = cond.get("pattern")
    mode = cond.get("mode", "search")
    flags = cond.get("flags", [])
    coerce = cond.get("coerce")  # None|"str"|"lower-str"
    max_len = cond.get("max_len")  # int|None
    engine_timeout_ms = cond.get("engine_timeout_ms")  # int|None

    if not isinstance(field, str) or not isinstance(pattern, str):
        raise ValueError("REGEX: 'field' y 'pattern' son obligatorios (string).")
    if mode not in ("search", "match", "fullmatch"):
        raise ValueError("REGEX.mode debe ser 'search'|'match'|'fullmatch'.")
    if coerce not in (None, "str", "lower-str"):
        raise ValueError("REGEX.coerce inválido.")
    if max_len is not None and (not isinstance(max_len, int) or max_len <= 0):
        raise ValueError("REGEX.max_len debe ser int > 0.")
    if engine_timeout_ms is not None:
        if not HAS_REGEX:
            # podés degradar a sin-timeout con warning, o rechazar
            raise ValueError("REGEX.engine_timeout_ms requiere el módulo 'regex'.")
        if not isinstance(engine_timeout_ms, int) or engine_timeout_ms <= 0:
            raise ValueError("REGEX.engine_timeout_ms debe ser int > 0.")

    flags_value = _compose_flags(flags)
    compiled = rx_mod.compile(pattern, flags_value)

    return RegexMatcher(
        field=field,
        pattern=pattern,
        mode=mode,
        flags_value=flags_value,
        coerce=coerce,
        max_len=max_len,
        engine_timeout_ms=engine_timeout_ms,
        compiled=compiled,
    )