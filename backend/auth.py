"""JWT-Authentifizierung für ScriptNext — Bearer + httpOnly-Cookie."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

COOKIE_NAME = "scriptnext_token"
COOKIE_MAX_AGE = 86400  # 24h


class TokenPayload(BaseModel):
    sub: str
    tenant_id: str
    scope: str = "scriptnext"
    rolle: str = "editor"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str


def hash_passwort(passwort: str) -> str:
    return pwd_context.hash(passwort)


def verify_passwort(passwort: str, hashed: str) -> bool:
    return pwd_context.verify(passwort, hashed)


def erstelle_token(benutzername: str, tenant_id: uuid.UUID, rolle: str = "editor") -> str:
    ablauf = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": benutzername,
        "tenant_id": str(tenant_id),
        "scope": "scriptnext",
        "rolle": rolle,
        "exp": ablauf,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode_token(token: str) -> TokenPayload:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Ungültiger oder abgelaufener Token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("scope") != "scriptnext":
            raise exc
        return TokenPayload(
            sub=payload["sub"],
            tenant_id=payload["tenant_id"],
            scope=payload["scope"],
            rolle=payload.get("rolle", "editor"),
        )
    except JWTError:
        raise exc


async def aktueller_nutzer(
    request: Request,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
) -> TokenPayload:
    """Liest Token zuerst aus httpOnly-Cookie, dann aus Bearer-Header."""
    token: Optional[str] = None

    cookie_token = request.cookies.get(COOKIE_NAME)
    if cookie_token:
        token = cookie_token
    elif credentials:
        token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nicht authentifiziert",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _decode_token(token)


async def admin_erforderlich(
    token_data: Annotated[TokenPayload, Depends(aktueller_nutzer)],
) -> TokenPayload:
    """Dependency: wirft 403 wenn Rolle nicht 'admin'."""
    if token_data.rolle != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin-Berechtigung erforderlich",
        )
    return token_data
