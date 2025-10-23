from __future__ import annotations
from dataclasses import dataclass
from time import perf_counter
from typing import Dict, Any, Optional, Callable

from .base import Matcher

LogFn = Callable[[str], None]  # ej. logger.debug

from utils.logs import setup_logger_json

logger = setup_logger_json("DEBUG", "kp_gateway_selector.matchers.debug")

@dataclass(frozen=True)
class DebugWrap(Matcher):
    """
    Envuelve cualquier Matcher y reporta:
      - path lógico (ALL->ANY->REGEX, etc.)
      - resultado True/False
      - duración en ms
      - claves leídas del ctx (opcional)
    Pensado para usar en simulador o cuando DEBUG_RULES=True.
    """
    inner: Matcher
    path: str                     # etiqueta jerárquica (p.ej. "ALL[0].ANY[1].REGEX")
    log: Optional[LogFn] = None   # por defecto no loguea (puede ser logger.debug)
    capture_ctx_keys: bool = False

    @property
    def name(self) -> str:
        return f"DBG({self.inner.name})"

    def __call__(self, ctx: Dict[str, Any]) -> bool:
        t0 = perf_counter()
        res = self.inner(ctx)
        dt_ms = (perf_counter() - t0) * 1000.0

        keys = list(ctx.keys()) if self.capture_ctx_keys else None
        if self.log:
            # Nota: no serializamos ctx entero para evitar PII.
            self.log(
                f"[rules-debug] path={self.path} matcher={self.inner} "
                f"result={res} time_ms={dt_ms:.3f}"
                + (f" ctx_keys={keys}" if keys is not None else "")
            )
        else:
            extra = {
                "path": self.path,
                "matcher": self.inner,
                "result": res,
                "time_ms": dt_ms,
            }
            if (keys is not None):
                extra["ctx_keys"] = keys
            logger.debug(f"debug wrap log for matcher {self.inner}", extra=extra)
        return res