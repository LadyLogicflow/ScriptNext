"""Rate-Limiting für ScriptNext (slowapi, in-memory)."""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _tenant_user_key(request: Request) -> str:
    """Begrenzt pro (Tenant, User) — fällt auf IP zurück wenn kein Token vorhanden."""
    try:
        from auth import _decode_token
        token = request.cookies.get("scriptnext_token")
        if not token:
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        if token:
            payload = _decode_token(token)
            return f"{payload.tenant_id}:{payload.sub}"
    except Exception:
        pass
    return get_remote_address(request)


limiter = Limiter(key_func=_tenant_user_key)
