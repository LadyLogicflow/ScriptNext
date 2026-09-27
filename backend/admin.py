"""Admin-Endpoints: Nutzer-Verwaltung (Sprint 3d)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import TokenPayload, admin_erforderlich, hash_passwort
from database import get_db
import models

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

ROLLEN = ("admin", "editor", "viewer")


# ── Schemas ───────────────────────────────────────────────────────────────────

class NutzerErstellen(BaseModel):
    benutzername: str = Field(min_length=3, max_length=100)
    passwort: str = Field(min_length=8)
    rolle: str = "editor"
    tenant_name: str = Field(min_length=1, max_length=200)


class RolleAendern(BaseModel):
    rolle: str


class NutzerAntwort(BaseModel):
    id: uuid.UUID
    benutzername: str
    rolle: str
    tenant_id: uuid.UUID
    erstellt_am: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/nutzer")
async def nutzer_liste(
    token_data: Annotated[TokenPayload, Depends(admin_erforderlich)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Listet alle Nutzer (Admin only)."""
    alle = (await db.scalars(select(models.Nutzer))).all()
    return {
        "gesamt": len(alle),
        "nutzer": [
            NutzerAntwort(
                id=n.id,
                benutzername=n.benutzername,
                rolle=n.rolle,
                tenant_id=n.tenant_id,
                erstellt_am=n.erstellt_am.isoformat(),
            ).model_dump()
            for n in alle
        ],
    }


@router.post("/nutzer", status_code=status.HTTP_201_CREATED)
async def nutzer_anlegen(
    body: NutzerErstellen,
    token_data: Annotated[TokenPayload, Depends(admin_erforderlich)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Legt neuen Nutzer mit eigenem Tenant an (Admin only)."""
    if body.rolle not in ROLLEN:
        raise HTTPException(400, f"Ungültige Rolle. Erlaubt: {', '.join(ROLLEN)}")

    existing = await db.scalar(
        select(models.Nutzer).where(models.Nutzer.benutzername == body.benutzername)
    )
    if existing:
        raise HTTPException(409, "Benutzername bereits vergeben")

    tenant = models.Tenant(name=body.tenant_name)
    db.add(tenant)
    await db.flush()

    nutzer = models.Nutzer(
        tenant_id=tenant.id,
        benutzername=body.benutzername,
        passwort_hash=hash_passwort(body.passwort),
        rolle=body.rolle,
    )
    db.add(nutzer)
    await db.commit()
    await db.refresh(nutzer)

    return NutzerAntwort(
        id=nutzer.id,
        benutzername=nutzer.benutzername,
        rolle=nutzer.rolle,
        tenant_id=nutzer.tenant_id,
        erstellt_am=nutzer.erstellt_am.isoformat(),
    ).model_dump()


@router.patch("/nutzer/{nutzer_id}")
async def rolle_aendern(
    nutzer_id: uuid.UUID,
    body: RolleAendern,
    token_data: Annotated[TokenPayload, Depends(admin_erforderlich)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Ändert die Rolle eines Nutzers (Admin only)."""
    if body.rolle not in ROLLEN:
        raise HTTPException(400, f"Ungültige Rolle. Erlaubt: {', '.join(ROLLEN)}")

    nutzer = await db.get(models.Nutzer, nutzer_id)
    if not nutzer:
        raise HTTPException(404, "Nutzer nicht gefunden")

    nutzer.rolle = body.rolle
    await db.commit()
    await db.refresh(nutzer)

    return NutzerAntwort(
        id=nutzer.id,
        benutzername=nutzer.benutzername,
        rolle=nutzer.rolle,
        tenant_id=nutzer.tenant_id,
        erstellt_am=nutzer.erstellt_am.isoformat(),
    ).model_dump()


@router.delete("/nutzer/{nutzer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def nutzer_loeschen(
    nutzer_id: uuid.UUID,
    token_data: Annotated[TokenPayload, Depends(admin_erforderlich)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Löscht einen Nutzer (Admin only). Eigenes Konto kann nicht gelöscht werden."""
    nutzer = await db.get(models.Nutzer, nutzer_id)
    if not nutzer:
        raise HTTPException(404, "Nutzer nicht gefunden")

    if nutzer.benutzername == token_data.sub:
        raise HTTPException(400, "Eigenes Konto kann nicht gelöscht werden")

    await db.delete(nutzer)
    await db.commit()
