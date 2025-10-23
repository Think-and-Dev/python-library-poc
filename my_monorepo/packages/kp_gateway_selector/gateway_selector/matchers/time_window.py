from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional, FrozenSet, Iterable
from datetime import datetime, time
from zoneinfo import ZoneInfo

from .base import Matcher, register_matcher

# ---------------------------
# Helpers internos
# ---------------------------

_DOW_MAP = {
    "mon": 0, "monday": 0,
    "tue": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}

def _parse_hms(s: str, tz: ZoneInfo) -> time:
    """
    Acepta "HH:MM" o "HH:MM:SS". Devuelve time con tzinfo.
    """
    parts = s.split(":")
    if len(parts) not in (2, 3):
        raise ValueError("TIME_WINDOW: formato de hora inválido (usa HH:MM o HH:MM:SS).")
    hh = int(parts[0]); mm = int(parts[1]); ss = int(parts[2]) if len(parts) == 3 else 0
    if not (0 <= hh <= 23 and 0 <= mm <= 59 and 0 <= ss <= 59):
        raise ValueError("TIME_WINDOW: valores de hora/minuto/segundo fuera de rango.")
    return time(hour=hh, minute=mm, second=ss, tzinfo=tz)

def _parse_days(days: Iterable[str]) -> FrozenSet[int]:
    """
    Convierte ["mon","tue",...], case-insensitive, a índices weekday() 0..6.
    """
    out = set()
    for d in days:
        key = str(d).strip().lower()
        if key not in _DOW_MAP:
            raise ValueError(f"TIME_WINDOW: día inválido '{d}'. Usa mon..sun.")
        out.add(_DOW_MAP[key])
    return frozenset(out)

# ---------------------------
# Matcher
# ---------------------------

@dataclass(frozen=True)
class TimeWindow(Matcher):
    """
    Matcher que valida si el tiempo actual (en una zona horaria dada) cae dentro
    de una ventana horaria, con soporte de cruce de medianoche y días de semana.

    Comportamiento:
    - Se obtiene el "ahora" en la tz indicada (o se toma `ctx["now"]` si está presente).
    - Se compara solo el componente horario (HH:MM[:SS]) respecto a `start` y `end`.
    - Si `start <= end`: ventana diurna (ej. 09:00–18:00).
    - Si `start > end`: ventana que cruza medianoche (ej. 22:00–06:00).
    - Si `days_of_week` está definido, también se filtra por día (0=Mon..6=Sun).

    Ejemplos (JSON):
    ----------------
    1) Ventana 09:00–18:00 hora São Paulo, cualquier día:
        {
          "type": "TIME_WINDOW",
          "impl": "v1",
          "tz": "America/Sao_Paulo",
          "start": "09:00",
          "end":   "18:00"
        }

    2) Ventana nocturna 22:00–06:00, solo lunes a viernes:
        {
          "type": "TIME_WINDOW",
          "tz": "America/Sao_Paulo",
          "start": "22:00",
          "end":   "06:00",
          "days_of_week": ["mon","tue","wed","thu","fri"]
        }

    Notas:
    - Para pruebas, podés pasar `ctx["now"] = datetime(..., tzinfo=<ZoneInfo>)`.
    - El tz se aplica al "ahora" si `ctx["now"]` no tiene tzinfo; si ya la tiene,
      se convierte (astimezone) a la tz del matcher para comparar correctamente.
    """

    # Zona horaria en la que se evalúa la ventana.
    tz: ZoneInfo

    # Hora de inicio (incluida), con tzinfo=tz.
    start: time

    # Hora de fin (incluida), con tzinfo=tz.
    end: time

    # Días de la semana permitidos (0=Mon..6=Sun). None significa "cualquier día".
    days_of_week: Optional[FrozenSet[int]] = None

    @property
    def name(self) -> str:
        return "TIME_WINDOW"

    def __call__(self, ctx: Dict[str, Any]) -> bool:
        # Obtener "ahora"
        now: Optional[datetime] = ctx.get("now")  # opcional, útil en tests/simulador. Analizar si no queremos usar un field configurable en este caso tmb.
        if now is None:
            now = datetime.now(self.tz)
        else:
            # Normalizar tz: si naive, asumir tz propia; si con tzinfo, convertir
            if now.tzinfo is None:
                now = now.replace(tzinfo=self.tz)
            else:
                now = now.astimezone(self.tz)

        # Filtrar por día si corresponde
        if self.days_of_week is not None:
            if now.weekday() not in self.days_of_week:
                return False

        # Comparación horaria (solo componente time con tz)
        now_t = now.timetz() if hasattr(now, "timetz") else now.time()

        if self.start <= self.end:
            # Ventana diurna (no cruza medianoche)
            return self.start <= now_t <= self.end
        else:
            # Cruza medianoche: válido si está después de start o antes de end
            return now_t >= self.start or now_t <= self.end

    def __str__(self) -> str:
        return f"TIME_WINDOW(tz={self.tz}, start={self.start}, end={self.end}, days_of_week={self.days_of_week})"

# ---------------------------
# Factory
# ---------------------------

@register_matcher("TIME_WINDOW", "v1")
def make_time_window(cond: dict) -> Matcher:
    tz_name = cond.get("tz")
    if not isinstance(tz_name, str):
        raise ValueError("TIME_WINDOW: 'tz' es obligatorio (string).")
    tz = ZoneInfo(tz_name)

    start_s = cond.get("start")
    end_s   = cond.get("end")
    if not isinstance(start_s, str) or not isinstance(end_s, str):
        raise ValueError("TIME_WINDOW: 'start' y 'end' deben ser strings HH:MM[:SS].")

    start = _parse_hms(start_s, tz)
    end   = _parse_hms(end_s, tz)

    days_cfg = cond.get("days_of_week")
    days: Optional[FrozenSet[int]] = None
    if days_cfg is not None:
        if not isinstance(days_cfg, (list, tuple)):
            raise ValueError("TIME_WINDOW: 'days_of_week' debe ser lista de strings.")
        days = _parse_days(days_cfg)

    return TimeWindow(
        tz=tz,
        start=start,
        end=end,
        days_of_week=days
    )