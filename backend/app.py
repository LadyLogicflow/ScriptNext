"""ScriptNext Backend — FastAPI-App."""
import asyncio
import logging
import uuid
from typing import Annotated

import os

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, status, BackgroundTasks, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth import (
    TokenPayload, TokenResponse, COOKIE_NAME, COOKIE_MAX_AGE,
    aktueller_nutzer, erstelle_token, hash_passwort, verify_passwort,
)
from config import settings
from database import get_db, engine, Base
import ingest as ingest_lib
import models
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from admin import router as admin_router
from rate_limit import limiter
from sharepoint import router as sharepoint_router
from rechtsquellen import router as rechtsquellen_router
from feedback import router as feedback_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="ScriptNext API",
    version="0.1.0",
    description="KI-gestützte Skript-Analyse. Mandantenfähig.",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_cors_origins = [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_PANDORA_PREFIX = os.environ.get("PANDORA_PREVIEW_PREFIX", "")


class _StripPrefixMiddleware(BaseHTTPMiddleware):
    """Strippt PANDORA_PREVIEW_PREFIX vom Pfad.

    Pandora leitet mit vollem Pfad weiter (/preview/.../api/v1/...),
    FastAPI kennt aber nur /api/v1/... — daher kürzen.
    """

    async def dispatch(self, request: Request, call_next):
        prefix = _PANDORA_PREFIX
        if prefix:
            path = request.scope.get("path", "")
            if path.startswith(prefix):
                request.scope["path"] = path[len(prefix):] or "/"
                raw = request.scope.get("raw_path", b"")
                encoded = prefix.encode()
                if raw.startswith(encoded):
                    request.scope["raw_path"] = raw[len(encoded):] or b"/"
        return await call_next(request)


if _PANDORA_PREFIX:
    app.add_middleware(_StripPrefixMiddleware)

app.include_router(admin_router)
app.include_router(sharepoint_router)
app.include_router(rechtsquellen_router)
app.include_router(feedback_router)


# ── Startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    from sqlalchemy import text
    from models import PGVECTOR_AVAILABLE
    async with engine.begin() as conn:
        if PGVECTOR_AVAILABLE:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    await _sicherstelle_dev_admin()


async def _sicherstelle_dev_admin():
    """Legt den Admin-Nutzer an wenn er noch nicht existiert (DEV-ONLY)."""
    if not settings.admin_passwort_hash:
        logger.warning("SCRIPTNEXT_ADMIN_PASSWORT_HASH nicht gesetzt — kein Admin angelegt")
        return
    from datetime import datetime, timezone
    from sqlalchemy import text
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT id FROM nutzer WHERE benutzername = :b"),
            {"b": settings.admin_benutzername},
        )
        if result.fetchone():
            return
        tenant_id = uuid.uuid4()
        jetzt = datetime.now(timezone.utc)
        await conn.execute(
            text("INSERT INTO tenants (id, name, erstellt_am) VALUES (:id, :name, :ts)"),
            {"id": str(tenant_id), "name": "Admin", "ts": jetzt},
        )
        await conn.execute(
            text("INSERT INTO nutzer (id, tenant_id, benutzername, passwort_hash, rolle, erstellt_am) VALUES (:id, :tid, :b, :h, :r, :ts)"),
            {
                "id": str(uuid.uuid4()),
                "tid": str(tenant_id),
                "b": settings.admin_benutzername,
                "h": settings.admin_passwort_hash,
                "r": "admin",
                "ts": jetzt,
            },
        )
        logger.info("Dev-Admin '%s' angelegt (Tenant %s)", settings.admin_benutzername, tenant_id)


# ── Schemas ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    benutzername: str
    passwort: str


class PasswortAendernRequest(BaseModel):
    altes_passwort: str
    neues_passwort: str


class ThemaSchema(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    titel: str
    beschreibung: str | None
    chunk_count: int
    dokument_id: uuid.UUID
    erstellt_am: str
    aktualisiert_am: str

    @classmethod
    def von_model(cls, t: models.Thema) -> "ThemaSchema":
        return cls(
            id=t.id,
            tenant_id=t.tenant_id,
            titel=t.titel,
            beschreibung=t.beschreibung,
            chunk_count=len(t.chunks),
            dokument_id=t.dokument_id,
            erstellt_am=t.erstellt_am.isoformat(),
            aktualisiert_am=t.aktualisiert_am.isoformat(),
        )


class ThemaUpdate(BaseModel):
    titel: str | None = None
    beschreibung: str | None = None


class MergeRequest(BaseModel):
    quell_ids: list[uuid.UUID]
    ziel_titel: str


class SplitRequest(BaseModel):
    titel_a: str
    titel_b: str
    chunk_ids_a: list[uuid.UUID]  # welche Chunks gehören zu Thema A


class SeminarGenerierenRequest(BaseModel):
    thema_id: uuid.UUID
    zielgruppe: str = "Mitarbeitende"
    dauer_minuten: int = 90


class SeminarAbschnittSchema(BaseModel):
    id: uuid.UUID
    reihenfolge: int
    typ: str
    titel: str
    inhalt: str | None
    w_frage: str | None
    dauer_minuten: int | None

    @classmethod
    def von_model(cls, a: models.SeminarAbschnitt) -> "SeminarAbschnittSchema":
        return cls(
            id=a.id,
            reihenfolge=a.reihenfolge,
            typ=a.typ,
            titel=a.titel,
            inhalt=a.inhalt,
            w_frage=a.w_frage,
            dauer_minuten=a.dauer_minuten,
        )


class SeminarSchema(BaseModel):
    id: uuid.UUID
    thema_id: uuid.UUID
    titel: str
    zielgruppe: str | None
    dauer_minuten: int | None
    lernziele: str | None
    abschnitte: list[SeminarAbschnittSchema]
    erstellt_am: str

    @classmethod
    def von_model(cls, s: models.Seminar) -> "SeminarSchema":
        return cls(
            id=s.id,
            thema_id=s.thema_id,
            titel=s.titel,
            zielgruppe=s.zielgruppe,
            dauer_minuten=s.dauer_minuten,
            lernziele=s.lernziele,
            abschnitte=[SeminarAbschnittSchema.von_model(a) for a in s.abschnitte],
            erstellt_am=s.erstellt_am.isoformat(),
        )


class DokumentStatus(BaseModel):
    dokument_id: uuid.UUID
    dateiname: str
    status: str
    themen_anzahl: int | None


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/api/v1/auth/login", response_model=TokenResponse, tags=["auth"])
@limiter.limit("20/minute")
async def login(request: Request, body: LoginRequest, response: Response, db: Annotated[AsyncSession, Depends(get_db)]):
    nutzer = await db.scalar(
        select(models.Nutzer).where(models.Nutzer.benutzername == body.benutzername)
    )
    if not nutzer or not verify_passwort(body.passwort, nutzer.passwort_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ungültige Anmeldedaten")
    token = erstelle_token(nutzer.benutzername, nutzer.tenant_id, nutzer.rolle)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return TokenResponse(access_token=token, tenant_id=str(nutzer.tenant_id))


@app.post("/api/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["auth"])
async def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/")


@app.post("/api/v1/auth/passwort-aendern", status_code=status.HTTP_204_NO_CONTENT, tags=["auth"])
async def passwort_aendern(
    body: PasswortAendernRequest,
    nutzer_token: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    nutzer = await db.scalar(
        select(models.Nutzer).where(models.Nutzer.benutzername == nutzer_token.sub)
    )
    if not nutzer or not verify_passwort(body.altes_passwort, nutzer.passwort_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Altes Passwort falsch")
    nutzer.passwort_hash = hash_passwort(body.neues_passwort)
    await db.commit()


# ── Upload ────────────────────────────────────────────────────────────────────

@app.post("/api/v1/upload", status_code=status.HTTP_202_ACCEPTED, response_model=DokumentStatus, tags=["dokumente"])
async def upload(
    background_tasks: BackgroundTasks,
    datei: Annotated[UploadFile, File()],
    nutzer_token: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if datei.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(400, "Nur PDF-Dateien erlaubt")

    pdf_bytes = await datei.read()
    if len(pdf_bytes) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(400, f"Datei überschreitet {settings.max_upload_mb} MB")

    dokument = models.Dokument(
        tenant_id=uuid.UUID(nutzer_token.tenant_id),
        dateiname=datei.filename or "upload.pdf",
        status="verarbeitung",
    )
    db.add(dokument)
    await db.commit()
    await db.refresh(dokument)

    background_tasks.add_task(_verarbeite_pdf, dokument.id, pdf_bytes, nutzer_token.tenant_id)

    return DokumentStatus(
        dokument_id=dokument.id,
        dateiname=dokument.dateiname,
        status="verarbeitung",
        themen_anzahl=None,
    )


async def _verarbeite_pdf(dokument_id: uuid.UUID, pdf_bytes: bytes, tenant_id: str):
    """Hintergrundaufgabe: Text extrahieren, chunken, embedden, Themen erkennen."""
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

            # Chunks in DB speichern
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

            # Embeddings (optional — kein API-Key = wird übersprungen)
            for chunk in chunk_modelle:
                emb = await ingest_lib.erstelle_embedding(
                    chunk.text, settings.openai_api_key, settings.embedding_model
                )
                if emb:
                    chunk.embedding = emb

            # Themen erkennen
            chunk_daten = [{"id": str(c.id), "text": c.text, "seite": c.seite} for c in chunk_modelle]
            themen_daten = ingest_lib.erkenne_themen(chunk_daten)

            thema_modelle = []
            for td in themen_daten:
                thema = models.Thema(
                    tenant_id=uuid.UUID(tenant_id),
                    dokument_id=dokument_id,
                    titel=td["titel"],
                    beschreibung=td["beschreibung"],
                )
                db.add(thema)
                thema_modelle.append((thema, td["chunk_ids"]))
            await db.flush()

            # Chunks den Themen zuordnen
            for thema, chunk_ids in thema_modelle:
                for cid in chunk_ids:
                    if cid:
                        await db.execute(
                            models.Chunk.__table__.update()
                            .where(models.Chunk.id == uuid.UUID(cid))
                            .values(thema_id=thema.id)
                        )

            # Dokument-Status aktualisieren
            dok = await db.get(models.Dokument, dokument_id)
            if dok:
                dok.status = "fertig"
                dok.themen_anzahl = len(thema_modelle)
            await db.commit()

        except Exception as e:
            logger.exception("Ingest-Fehler für Dokument %s", dokument_id)
            async with AsyncSessionLocal() as err_db:
                dok = await err_db.get(models.Dokument, dokument_id)
                if dok:
                    dok.status = "fehler"
                    dok.fehler_meldung = str(e)[:500]
                    await err_db.commit()


@app.get("/api/v1/dokumente/{dokument_id}", response_model=DokumentStatus, tags=["dokumente"])
async def dokument_status(
    dokument_id: uuid.UUID,
    nutzer_token: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    dok = await db.get(models.Dokument, dokument_id)
    if not dok:
        raise HTTPException(404, "Dokument nicht gefunden")
    if str(dok.tenant_id) != nutzer_token.tenant_id:
        raise HTTPException(403, "Zugriff verweigert")
    return DokumentStatus(
        dokument_id=dok.id,
        dateiname=dok.dateiname,
        status=dok.status,
        themen_anzahl=dok.themen_anzahl,
    )


# ── Themen ────────────────────────────────────────────────────────────────────

@app.get("/api/v1/themen", tags=["themen"])
async def themen_liste(
    nutzer_token: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
    dokument_id: uuid.UUID | None = None,
    seite: int = 1,
    pro_seite: int = 50,
):
    if pro_seite > 200:
        pro_seite = 200
    tenant_id = uuid.UUID(nutzer_token.tenant_id)

    q = (
        select(models.Thema)
        .where(models.Thema.tenant_id == tenant_id)
        .options(selectinload(models.Thema.chunks))
    )
    if dokument_id:
        q = q.where(models.Thema.dokument_id == dokument_id)

    gesamt = await db.scalar(
        select(func.count()).select_from(
            select(models.Thema).where(models.Thema.tenant_id == tenant_id).subquery()
        )
    )
    themen = (await db.scalars(q.offset((seite - 1) * pro_seite).limit(pro_seite))).all()

    return {
        "gesamt": gesamt or 0,
        "seite": seite,
        "themen": [ThemaSchema.von_model(t) for t in themen],
    }


@app.patch("/api/v1/themen/{thema_id}", response_model=ThemaSchema, tags=["themen"])
async def thema_aktualisieren(
    thema_id: uuid.UUID,
    body: ThemaUpdate,
    nutzer_token: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    thema = await db.scalar(
        select(models.Thema)
        .where(models.Thema.id == thema_id)
        .options(selectinload(models.Thema.chunks))
    )
    if not thema:
        raise HTTPException(404, "Thema nicht gefunden")
    if str(thema.tenant_id) != nutzer_token.tenant_id:
        raise HTTPException(403, "Zugriff verweigert")

    if body.titel is not None:
        thema.titel = body.titel
    if body.beschreibung is not None:
        thema.beschreibung = body.beschreibung
    await db.commit()
    await db.refresh(thema)
    return ThemaSchema.von_model(thema)


@app.delete("/api/v1/themen/{thema_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["themen"])
async def thema_loeschen(
    thema_id: uuid.UUID,
    nutzer_token: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    thema = await db.get(models.Thema, thema_id)
    if not thema:
        raise HTTPException(404, "Thema nicht gefunden")
    if str(thema.tenant_id) != nutzer_token.tenant_id:
        raise HTTPException(403, "Zugriff verweigert")
    await db.delete(thema)
    await db.commit()


@app.post("/api/v1/themen/merge", response_model=ThemaSchema, tags=["themen"])
async def themen_merge(
    body: MergeRequest,
    nutzer_token: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if len(body.quell_ids) < 2:
        raise HTTPException(400, "Mindestens 2 Themen zum Zusammenführen nötig")

    tenant_id = uuid.UUID(nutzer_token.tenant_id)
    quell_themen = (
        await db.scalars(
            select(models.Thema)
            .where(models.Thema.id.in_(body.quell_ids))
            .options(selectinload(models.Thema.chunks))
        )
    ).all()

    if len(quell_themen) != len(body.quell_ids):
        raise HTTPException(404, "Ein oder mehrere Themen nicht gefunden")
    for t in quell_themen:
        if t.tenant_id != tenant_id:
            raise HTTPException(403, "Zugriff verweigert")

    dokument_id = quell_themen[0].dokument_id

    # Neues Thema anlegen
    neues_thema = models.Thema(
        tenant_id=tenant_id,
        dokument_id=dokument_id,
        titel=body.ziel_titel,
    )
    db.add(neues_thema)
    await db.flush()

    # Chunks umhängen
    alle_chunks = [c for t in quell_themen for c in t.chunks]
    for chunk in alle_chunks:
        chunk.thema_id = neues_thema.id

    # Quell-Themen löschen (Chunks bleiben erhalten)
    for t in quell_themen:
        await db.delete(t)

    await db.commit()

    neues_thema_frisch = await db.scalar(
        select(models.Thema)
        .where(models.Thema.id == neues_thema.id)
        .options(selectinload(models.Thema.chunks))
    )
    return ThemaSchema.von_model(neues_thema_frisch)


# ── Themen Split ─────────────────────────────────────────────────────────────

@app.post("/api/v1/themen/{thema_id}/split", tags=["themen"])
async def thema_split(
    thema_id: uuid.UUID,
    body: SplitRequest,
    nutzer_token: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    thema = await db.scalar(
        select(models.Thema)
        .where(models.Thema.id == thema_id)
        .options(selectinload(models.Thema.chunks))
    )
    if not thema:
        raise HTTPException(404, "Thema nicht gefunden")
    if str(thema.tenant_id) != nutzer_token.tenant_id:
        raise HTTPException(403, "Zugriff verweigert")
    if not body.chunk_ids_a:
        raise HTTPException(400, "chunk_ids_a darf nicht leer sein")

    tenant_id = uuid.UUID(nutzer_token.tenant_id)
    chunk_ids_a_set = {str(cid) for cid in body.chunk_ids_a}
    chunks_a = [c for c in thema.chunks if str(c.id) in chunk_ids_a_set]
    chunks_b = [c for c in thema.chunks if str(c.id) not in chunk_ids_a_set]

    if not chunks_a or not chunks_b:
        raise HTTPException(400, "Beide Teilthemen müssen mindestens einen Chunk enthalten")

    # Thema A: das ursprüngliche umbenennen
    thema.titel = body.titel_a
    await db.flush()

    # Thema B: neues anlegen
    thema_b = models.Thema(
        tenant_id=tenant_id,
        dokument_id=thema.dokument_id,
        titel=body.titel_b,
    )
    db.add(thema_b)
    await db.flush()

    # Chunks zuweisen
    for chunk in chunks_b:
        chunk.thema_id = thema_b.id

    await db.commit()

    thema_a_frisch = await db.scalar(
        select(models.Thema).where(models.Thema.id == thema_id).options(selectinload(models.Thema.chunks))
    )
    thema_b_frisch = await db.scalar(
        select(models.Thema).where(models.Thema.id == thema_b.id).options(selectinload(models.Thema.chunks))
    )
    return {
        "thema_a": ThemaSchema.von_model(thema_a_frisch),
        "thema_b": ThemaSchema.von_model(thema_b_frisch),
    }


# ── Seminare ──────────────────────────────────────────────────────────────────

@app.post("/api/v1/seminare/generieren", response_model=SeminarSchema, tags=["seminare"])
@limiter.limit("10/minute")
async def seminar_generieren(
    request: Request,
    body: SeminarGenerierenRequest,
    nutzer_token: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    import ki as ki_lib

    thema = await db.scalar(
        select(models.Thema)
        .where(models.Thema.id == body.thema_id)
        .options(selectinload(models.Thema.chunks))
    )
    if not thema:
        raise HTTPException(404, "Thema nicht gefunden")
    if str(thema.tenant_id) != nutzer_token.tenant_id:
        raise HTTPException(403, "Zugriff verweigert")

    chunk_texte = [c.text for c in thema.chunks]
    ergebnis = await ki_lib.generiere_seminar(
        thema_titel=thema.titel,
        chunk_texte=chunk_texte,
        zielgruppe=body.zielgruppe,
        dauer_minuten=body.dauer_minuten,
        api_key=settings.anthropic_api_key,
    )

    seminar = models.Seminar(
        tenant_id=uuid.UUID(nutzer_token.tenant_id),
        thema_id=thema.id,
        titel=ergebnis["titel"],
        zielgruppe=ergebnis["zielgruppe"],
        dauer_minuten=ergebnis["dauer_minuten"],
        lernziele=ergebnis["lernziele"],
    )
    db.add(seminar)
    await db.flush()

    for ab_dict in ergebnis["abschnitte"]:
        abschnitt = models.SeminarAbschnitt(
            seminar_id=seminar.id,
            reihenfolge=ab_dict["reihenfolge"],
            typ=ab_dict["typ"],
            titel=ab_dict["titel"],
            inhalt=ab_dict.get("inhalt"),
            w_frage=ab_dict.get("w_frage"),
            dauer_minuten=ab_dict.get("dauer_minuten"),
        )
        db.add(abschnitt)

    await db.commit()

    seminar_frisch = await db.scalar(
        select(models.Seminar)
        .where(models.Seminar.id == seminar.id)
        .options(selectinload(models.Seminar.abschnitte))
    )
    return SeminarSchema.von_model(seminar_frisch)


@app.get("/api/v1/seminare/{seminar_id}", response_model=SeminarSchema, tags=["seminare"])
async def seminar_abrufen(
    seminar_id: uuid.UUID,
    nutzer_token: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    seminar = await db.scalar(
        select(models.Seminar)
        .where(models.Seminar.id == seminar_id)
        .options(selectinload(models.Seminar.abschnitte))
    )
    if not seminar:
        raise HTTPException(404, "Seminar nicht gefunden")
    if str(seminar.tenant_id) != nutzer_token.tenant_id:
        raise HTTPException(403, "Zugriff verweigert")
    return SeminarSchema.von_model(seminar)


# ── Export ────────────────────────────────────────────────────────────────────

@app.get("/api/v1/export/word/{seminar_id}", tags=["export"])
async def export_word(
    seminar_id: uuid.UUID,
    nutzer_token: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from fastapi.responses import StreamingResponse
    import export as export_lib

    seminar = await db.scalar(
        select(models.Seminar)
        .where(models.Seminar.id == seminar_id)
        .options(selectinload(models.Seminar.abschnitte))
    )
    if not seminar:
        raise HTTPException(404, "Seminar nicht gefunden")
    if str(seminar.tenant_id) != nutzer_token.tenant_id:
        raise HTTPException(403, "Zugriff verweigert")

    docx_bytes = export_lib.erstelle_word_export(seminar)
    dateiname = f"{seminar.titel[:50].replace(' ', '_')}.docx"
    return StreamingResponse(
        iter([docx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{dateiname}"'},
    )


@app.get("/api/v1/export/pptx/{seminar_id}", tags=["export"])
async def export_pptx(
    seminar_id: uuid.UUID,
    nutzer_token: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from fastapi.responses import StreamingResponse
    import export as export_lib

    seminar = await db.scalar(
        select(models.Seminar)
        .where(models.Seminar.id == seminar_id)
        .options(selectinload(models.Seminar.abschnitte))
    )
    if not seminar:
        raise HTTPException(404, "Seminar nicht gefunden")
    if str(seminar.tenant_id) != nutzer_token.tenant_id:
        raise HTTPException(403, "Zugriff verweigert")

    pptx_bytes = export_lib.erstelle_pptx_export(seminar)
    dateiname = f"{seminar.titel[:50].replace(' ', '_')}.pptx"
    return StreamingResponse(
        iter([pptx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{dateiname}"'},
    )


# ── Rechtsquellen ─────────────────────────────────────────────────────────────

@app.get("/api/v1/rechtsquellen", tags=["rechtsquellen"])
async def rechtsquellen_liste(
    nutzer_token: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
    gesetz: str | None = None,
):
    q = select(models.Rechtsquelle)
    if gesetz:
        q = q.where(models.Rechtsquelle.gesetz.ilike(f"%{gesetz}%"))
    quellen = (await db.scalars(q.limit(100))).all()
    return {
        "gesamt": len(quellen),
        "rechtsquellen": [
            {
                "id": str(r.id),
                "titel": r.titel,
                "paragraph": r.paragraph,
                "gesetz": r.gesetz,
                "fundstelle": r.fundstelle,
                "gueltig_ab": r.gueltig_ab.isoformat() if r.gueltig_ab else None,
            }
            for r in quellen
        ],
    }


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "version": "0.1.0"}
