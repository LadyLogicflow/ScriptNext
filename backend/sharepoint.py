"""Microsoft SharePoint-Anbindung via Graph API (Device-Code-Flow)."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import TokenPayload, aktueller_nutzer
from config import settings
from database import get_db
import ingest as ingest_lib
import models

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.microsoft.com/v1.0"
SP_SCOPES = ["Files.Read.All", "Sites.Read.All"]

# In-memory Device-Code-Sessions: session_id -> {flow, app, tenant_id}
_sessions: dict[str, dict] = {}

try:
    from msal import PublicClientApplication
    MSAL_AVAILABLE = True
except ImportError:
    MSAL_AVAILABLE = False

router = APIRouter(prefix="/api/v1/sharepoint", tags=["sharepoint"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_msal_app() -> "PublicClientApplication":
    if not MSAL_AVAILABLE:
        raise HTTPException(status_code=503, detail="msal-Bibliothek nicht installiert")
    if not settings.sharepoint_client_id:
        raise HTTPException(status_code=503, detail="SCRIPTNEXT_SHAREPOINT_CLIENT_ID nicht konfiguriert")
    return PublicClientApplication(
        client_id=settings.sharepoint_client_id,
        authority=f"https://login.microsoftonline.com/{settings.sharepoint_authority}",
    )


def _encrypt_token(token_json: str) -> str:
    if not settings.sharepoint_token_key:
        return token_json
    from cryptography.fernet import Fernet
    return Fernet(settings.sharepoint_token_key.encode()).encrypt(token_json.encode()).decode()


def _decrypt_token(encrypted: str) -> str:
    if not settings.sharepoint_token_key:
        return encrypted
    from cryptography.fernet import Fernet
    return Fernet(settings.sharepoint_token_key.encode()).decrypt(encrypted.encode()).decode()


async def _access_token_fuer_tenant(tenant_id: str, db: AsyncSession) -> str:
    """Lädt gespeicherten MSAL-Cache und holt ein frisches Access-Token."""
    row = await db.scalar(
        select(models.SharepointToken).where(
            models.SharepointToken.tenant_id == uuid.UUID(tenant_id)
        )
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Keine SharePoint-Verbindung. Bitte zuerst unter /sharepoint verbinden.",
        )
    token_cache_json = _decrypt_token(row.encrypted_token)
    app = _get_msal_app()
    app.token_cache.deserialize(token_cache_json)
    accounts = app.get_accounts()
    if not accounts:
        raise HTTPException(status_code=403, detail="Token ungültig. Bitte neu verbinden.")
    result = app.acquire_token_silent(SP_SCOPES, account=accounts[0])
    if not result or "error" in result:
        raise HTTPException(status_code=403, detail="Token konnte nicht erneuert werden. Bitte neu verbinden.")
    return result["access_token"]


# ── Schemas ───────────────────────────────────────────────────────────────────

class OrdnerItem(BaseModel):
    id: str
    name: str
    typ: str  # "site" | "drive" | "ordner" | "datei"
    kinder_vorhanden: bool
    groesse_bytes: int | None = None


class ImportRequest(BaseModel):
    drive_id: str   # ID des SharePoint-Drives
    ordner_ids: list[str]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/verbindung", tags=["sharepoint"])
async def verbindung_starten(
    token_data: Annotated[TokenPayload, Depends(aktueller_nutzer)],
):
    """Startet Microsoft Device-Code-Flow. Gibt user_code + verification_uri zurück."""
    app = _get_msal_app()
    flow = app.initiate_device_flow(scopes=SP_SCOPES)
    if "error" in flow:
        raise HTTPException(
            status_code=503,
            detail=f"Device-Code-Flow fehlgeschlagen: {flow.get('error_description', flow.get('error'))}",
        )
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {"flow": flow, "app": app, "tenant_id": str(token_data.tenant_id)}
    return {
        "session_id": session_id,
        "user_code": flow["user_code"],
        "verification_uri": flow["verification_uri"],
        "expires_in": flow.get("expires_in", 900),
        "message": flow.get("message", ""),
    }


@router.get("/verbindung/status", tags=["sharepoint"])
async def verbindung_status(
    session_id: str,
    token_data: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Prüft ob Device-Code-Auth abgeschlossen ist. Frontend pollt alle 5s."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden oder abgelaufen")
    if session["tenant_id"] != str(token_data.tenant_id):
        raise HTTPException(status_code=403, detail="Session gehört nicht zu diesem Tenant")

    app = session["app"]
    result = app.acquire_token_by_device_flow(session["flow"], timeout=0)

    if "error" in result:
        err = result.get("error", "")
        if err == "authorization_pending":
            return {"status": "pending", "token_gespeichert": False}
        if err in ("expired_token", "code_expired"):
            _sessions.pop(session_id, None)
            return {"status": "expired", "token_gespeichert": False}
        raise HTTPException(status_code=503, detail=f"Auth-Fehler: {result.get('error_description', err)}")

    # Erfolgreich — Token in DB speichern
    token_cache_json = app.token_cache.serialize()
    encrypted = _encrypt_token(token_cache_json)

    expires_at = None
    if result.get("expires_in"):
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(result["expires_in"]))

    account_upn: str | None = None
    if result.get("id_token_claims"):
        claims = result["id_token_claims"]
        account_upn = claims.get("preferred_username") or claims.get("upn")

    existing = await db.scalar(
        select(models.SharepointToken).where(
            models.SharepointToken.tenant_id == uuid.UUID(session["tenant_id"])
        )
    )
    if existing:
        existing.encrypted_token = encrypted
        existing.expires_at = expires_at
        existing.account_upn = account_upn
        existing.aktualisiert_am = datetime.now(timezone.utc)
    else:
        db.add(models.SharepointToken(
            tenant_id=uuid.UUID(session["tenant_id"]),
            encrypted_token=encrypted,
            expires_at=expires_at,
            account_upn=account_upn,
        ))
    await db.commit()
    _sessions.pop(session_id, None)

    return {"status": "authorized", "token_gespeichert": True, "konto": account_upn}


@router.get("/ordner", tags=["sharepoint"])
async def ordner_listen(
    token_data: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
    site_id: str | None = None,
    drive_id: str | None = None,
    parent_id: str | None = None,
):
    """Listet SharePoint-Sites, Drives oder Ordner-Inhalte."""
    access_token = await _access_token_fuer_tenant(str(token_data.tenant_id), db)
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(timeout=30) as client:
        if not site_id:
            r = await client.get(f"{GRAPH_API}/sites?search=*", headers=headers)
            r.raise_for_status()
            items = [
                OrdnerItem(id=s["id"], name=s.get("displayName", s.get("name", "")), typ="site", kinder_vorhanden=True)
                for s in r.json().get("value", [])
            ]
        elif not drive_id:
            r = await client.get(f"{GRAPH_API}/sites/{site_id}/drives", headers=headers)
            r.raise_for_status()
            items = [
                OrdnerItem(id=d["id"], name=d.get("name", d.get("driveType", "Drive")), typ="drive", kinder_vorhanden=True)
                for d in r.json().get("value", [])
            ]
        elif not parent_id:
            r = await client.get(f"{GRAPH_API}/drives/{drive_id}/root/children", headers=headers)
            r.raise_for_status()
            items = _parse_ordner_items(r.json().get("value", []))
        else:
            r = await client.get(f"{GRAPH_API}/drives/{drive_id}/items/{parent_id}/children", headers=headers)
            r.raise_for_status()
            items = _parse_ordner_items(r.json().get("value", []))

    return {"items": [i.model_dump() for i in items]}


def _parse_ordner_items(raw: list[dict]) -> list[OrdnerItem]:
    result = []
    for item in raw:
        typ = "ordner" if "folder" in item else "datei"
        kinder = typ == "ordner" and item.get("folder", {}).get("childCount", 0) > 0
        result.append(OrdnerItem(
            id=item["id"],
            name=item["name"],
            typ=typ,
            kinder_vorhanden=kinder,
            groesse_bytes=item.get("size"),
        ))
    return result


@router.post("/import", status_code=status.HTTP_202_ACCEPTED, tags=["sharepoint"])
async def dateien_importieren(
    payload: ImportRequest,
    background_tasks: BackgroundTasks,
    token_data: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Importiert alle PDFs aus den angegebenen SharePoint-Ordnern als Wissensquellen."""
    access_token = await _access_token_fuer_tenant(str(token_data.tenant_id), db)
    headers = {"Authorization": f"Bearer {access_token}"}

    importiert = 0
    uebersprungen = 0
    fehler: list[str] = []

    async with httpx.AsyncClient(timeout=60) as client:
        for ordner_id in payload.ordner_ids:
            try:
                r = await client.get(
                    f"{GRAPH_API}/drives/{payload.drive_id}/items/{ordner_id}/children",
                    headers=headers,
                )
                r.raise_for_status()

                for item in r.json().get("value", []):
                    if "file" not in item:
                        continue
                    dateiname: str = item.get("name", "")
                    if not dateiname.lower().endswith(".pdf"):
                        uebersprungen += 1
                        continue

                    dl_url = item.get("@microsoft.graph.downloadUrl")
                    if not dl_url:
                        fehler.append(f"{dateiname}: kein Download-Link")
                        continue

                    file_r = await client.get(dl_url, follow_redirects=True)
                    file_r.raise_for_status()

                    # Dokument-Eintrag anlegen
                    dokument = models.Dokument(
                        tenant_id=uuid.UUID(str(token_data.tenant_id)),
                        dateiname=dateiname,
                        status="verarbeitung",
                    )
                    db.add(dokument)
                    await db.flush()
                    await db.refresh(dokument)

                    background_tasks.add_task(
                        _verarbeite_sharepoint_pdf,
                        dokument.id,
                        file_r.content,
                        str(token_data.tenant_id),
                    )
                    importiert += 1

            except httpx.HTTPStatusError as e:
                fehler.append(f"Ordner {ordner_id}: HTTP {e.response.status_code}")
            except Exception as e:
                logger.exception("Import-Fehler für Ordner %s", ordner_id)
                fehler.append(f"Ordner {ordner_id}: {type(e).__name__}")

    await db.commit()
    return {"importiert": importiert, "uebersprungen": uebersprungen, "fehler": fehler}


async def _verarbeite_sharepoint_pdf(dokument_id: uuid.UUID, pdf_bytes: bytes, tenant_id: str):
    """Hintergrundaufgabe: Text extrahieren, chunken, Themen erkennen."""
    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            seiten = await asyncio.get_event_loop().run_in_executor(
                None, ingest_lib.extrahiere_text, pdf_bytes
            )
            chunk_dicts = list(ingest_lib.erstelle_chunks(
                seiten,
                chunk_groesse=settings.chunk_groesse,
                overlap=settings.chunk_overlap,
            ))

            chunk_modelle = []
            for cd in chunk_dicts:
                chunk = models.Chunk(
                    id=uuid.uuid4(),
                    tenant_id=uuid.UUID(tenant_id),
                    dokument_id=dokument_id,
                    text=cd["text"],
                    seite=cd["seite"],
                    chunk_index=cd["chunk_index"],
                )
                db.add(chunk)
                chunk_modelle.append(chunk)
            await db.flush()

            for chunk in chunk_modelle:
                emb = await ingest_lib.erstelle_embedding(
                    chunk.text, settings.openai_api_key, settings.embedding_model
                )
                if emb:
                    chunk.embedding = emb

            chunk_daten = [{"id": str(c.id), "text": c.text, "seite": c.seite} for c in chunk_modelle]
            themen_daten = ingest_lib.erkenne_themen(chunk_daten)

            for td in themen_daten:
                thema = models.Thema(
                    id=uuid.UUID(td["id"]),
                    tenant_id=uuid.UUID(tenant_id),
                    dokument_id=dokument_id,
                    titel=td["titel"],
                    beschreibung=td.get("beschreibung"),
                )
                db.add(thema)
                await db.flush()
                for chunk in chunk_modelle:
                    if str(chunk.id) in (td.get("chunk_ids") or []):
                        chunk.thema_id = thema.id

            dok = await db.get(models.Dokument, dokument_id)
            if dok:
                dok.status = "fertig"
                dok.themen_anzahl = len(themen_daten)
            await db.commit()

        except Exception:
            logger.exception("Fehler beim Verarbeiten von SharePoint-Dokument %s", dokument_id)
            async with AsyncSessionLocal() as err_db:
                dok = await err_db.get(models.Dokument, dokument_id)
                if dok:
                    dok.status = "fehler"
                    await err_db.commit()
