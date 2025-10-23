
from typing import Any, Dict

def _get_field(ctx: Dict[str, Any], path: str) -> Any:
    # Soporta paths simples "api_user_id" o anidados "request.headers.x"
    cur = ctx
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur