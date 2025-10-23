from .pix_errors import (
    PixValidationAuthFailure,
    PixValidationBadPayload,
    PixUpstreamError,
    PixKeyQRExpire
)
from enum import Enum

VALIDATION_CODE_MAP = {
    "E_AUTH": PixValidationAuthFailure,
    "E_PAYLOAD": PixValidationBadPayload,
    "E_PPROV": PixUpstreamError,
    "E_DECODE":PixKeyQRExpire
}

class CacheEventType(str, Enum):
    TOTAL_CALLS = "total_calls"
    CACHE_HIT = "cache_hit"
    CACHE_INVALID = "cache_invalid"
    NO_CACHE_HIT = "no_cache_hit"
    NO_CACHE_INVALID = "no_cache_invalid"
    PIX_KEY_INVALID_FORMAT = "pix_key_invalid_format"

class Currency(Enum):
    BRL = "BRL"
    USDT = "USDT"
class TTLUnit(Enum):
    SECONDS = "ex"
    MILLISECONDS = "px"

GATEWAY_FEE = 0.005
KP_FEE = 0.01  # POR AHORA SE PONE ESTE VALOR GENERAL QUE HAY QUE HACER MODULAR
MINIMUN_USDT_TO_SEND: float = 0.5
ORACLE_MIN_CACHE_MS = 200
