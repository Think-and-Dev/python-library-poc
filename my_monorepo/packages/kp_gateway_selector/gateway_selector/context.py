from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Literal, Optional, TypedDict
from typing_extensions import NotRequired # Not available in 'typing' module for Python < 3.11

from fastapi import Request

from utils.pix_key_types import PixKeyTypes

PixKeyType = Literal[
    PixKeyTypes.QRCODE,
    PixKeyTypes.QRCODE_STATIC,
    PixKeyTypes.QRCODE_DYNAMIC,
    PixKeyTypes.EMAIL,
    PixKeyTypes.PHONE,
    PixKeyTypes.CPF,
    PixKeyTypes.CNPJ,
    PixKeyTypes.EVP,
]

class GatewaySelectorCtx(TypedDict, total=False):
    """
    Contexto tipado que consumen los matchers y el selector.
    Todos los campos son opcionales para permitir construcción incremental,
    pero los matchers validan lo que necesitan.
    """
    api_user_id: NotRequired[int]          # ID del cliente (routing principal)
    pix_key: NotRequired[str]              # clave/QR usada en la operación
    pix_key_type: NotRequired[PixKeyType]  # tipo de pix_key
    amount: NotRequired[Decimal | int | str]  # monto; tu matcher lo coercea
    now: NotRequired[datetime]             # override de "ahora" (tests/simulador)
    env: NotRequired[Literal["prod", "staging", "dev"]]
    request: NotRequired[Request]      # metadata de la request
    # libre para extensiones
    extra: NotRequired[Dict[str, Any]]

def make_ctx(
    *,
    api_user_id: Optional[int] = None,
    pix_key: Optional[str] = None,
    pix_key_type: Optional[PixKeyType] = None,
    amount: Optional[Decimal | int | str] = None,
    now: Optional[datetime] = None,
    env: Optional[str] = None,
    request: Optional[Request] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> GatewaySelectorCtx:
    ctx: GatewaySelectorCtx = {}
    if api_user_id is not None: ctx["api_user_id"] = api_user_id
    if pix_key is not None: ctx["pix_key"] = pix_key
    if pix_key_type is not None: ctx["pix_key_type"] = pix_key_type
    if amount is not None: ctx["amount"] = amount
    if now is not None: ctx["now"] = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    if env is not None: ctx["env"] = env  # Literal validated elsewhere
    if request is not None: ctx["request"] = request
    if extra is not None: ctx["extra"] = extra
    return ctx
