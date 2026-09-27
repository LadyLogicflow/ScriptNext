"""JWT-Authentifizierung für ScriptNext."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


class TokenPayload(BaseModel):
    sub: str          # benutzername
    tenant_id: str
    scope: str = "scriptnext"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str


def hash_passwort(passwort: str) -> str:
    return pwd_context.hash(passwort)


def verify_passwort(passwort: str, hashed: str) -> bool:
    return pwd_context.verify(passwort, hashed)


def erstelle_token(benutzername: str, tenant_id: uuid.UUID) -> str:
    ablauf = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": benutzername,
        "tenant_id": str(tenant_id),
        "scope": "scriptnext",
        "exp": ablauf,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def aktueller_nutzer(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> TokenPayload:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Ungültiger oder abgelaufener Token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("scope") != "scriptnext":
            raise exc
        return TokenPayload(
            sub=payload["sub"],
            tenant_id=payload["tenant_id"],
            scope=payload["scope"],
        )
    except JWTError:
        raise exc
