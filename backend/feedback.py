"""Feedback-Schleife & Themen-Versionierung (Etappe 3c)."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import TokenPayload, aktueller_nutzer
from database import get_db
import models

router = APIRouter(tags=["feedback"])

BEWERTUNGEN = ("gut", "zu_langweilig", "falsche_ebene")
VERALTET_SCHWELLE_TAGE = 365  # Chunk gilt als veraltet nach 1 Jahr


# ── Schemas ───────────────────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    bewertung: str
    kommentar: str | None = Field(default=None, max_length=1000)


class FeedbackStats(BaseModel):
    gesamt: int
    gut: int
    zu_langweilig: int
    falsche_ebene: int
    letztes_feedback: str | None


class VeraltetItem(BaseModel):
    chunk_id: uuid.UUID
    thema_id: uuid.UUID | None
    thema_titel: str | None
    quelldatum: str | None
    veraltet_seit_tagen: int
    vorschlag: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/api/v1/seminare/{seminar_id}/feedback", status_code=status.HTTP_201_CREATED)
async def feedback_speichern(
    seminar_id: uuid.UUID,
    body: FeedbackRequest,
    token_data: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Speichert Nutzerfeedback zu einem Seminar."""
    if body.bewertung not in BEWERTUNGEN:
        raise HTTPException(
            status_code=400,
            detail=f"Ungültige Bewertung. Erlaubt: {', '.join(BEWERTUNGEN)}",
        )

    seminar = await db.get(models.Seminar, seminar_id)
    if not seminar or str(seminar.tenant_id) != str(token_data.tenant_id):
        raise HTTPException(status_code=404, detail="Seminar nicht gefunden")

    fb = models.SeminarFeedback(
        tenant_id=uuid.UUID(str(token_data.tenant_id)),
        seminar_id=seminar_id,
        bewertung=body.bewertung,
        kommentar=body.kommentar,
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)

    return {"id": str(fb.id), "gespeichert_am": fb.erstellt_am.isoformat()}


@router.get("/api/v1/seminare/{seminar_id}/feedback")
async def feedback_statistik(
    seminar_id: uuid.UUID,
    token_data: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Gibt aggregierte Feedback-Statistik für ein Seminar zurück."""
    seminar = await db.get(models.Seminar, seminar_id)
    if not seminar or str(seminar.tenant_id) != str(token_data.tenant_id):
        raise HTTPException(status_code=404, detail="Seminar nicht gefunden")

    rows = await db.scalars(
        select(models.SeminarFeedback).where(
            models.SeminarFeedback.seminar_id == seminar_id
        ).order_by(models.SeminarFeedback.erstellt_am.desc())
    )
    alle = list(rows)

    zählung = {b: 0 for b in BEWERTUNGEN}
    for fb in alle:
        if fb.bewertung in zählung:
            zählung[fb.bewertung] += 1

    letztes = alle[0].erstellt_am.date().isoformat() if alle else None

    return FeedbackStats(
        gesamt=len(alle),
        gut=zählung["gut"],
        zu_langweilig=zählung["zu_langweilig"],
        falsche_ebene=zählung["falsche_ebene"],
        letztes_feedback=letztes,
    ).model_dump()


@router.get("/api/v1/chunks/veraltet")
async def chunks_veraltet(
    token_data: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
):
    """Listet Chunks deren Quelldatum älter als 365 Tage ist."""
    schwelle = datetime.now(timezone.utc) - timedelta(days=VERALTET_SCHWELLE_TAGE)

    stmt = (
        select(models.Chunk)
        .where(
            models.Chunk.tenant_id == uuid.UUID(str(token_data.tenant_id)),
            models.Chunk.quelldatum < schwelle,
        )
        .limit(limit)
    )
    rows = await db.scalars(stmt)
    chunks = list(rows)

    heute = datetime.now(timezone.utc)
    items = []
    for chunk in chunks:
        thema_titel = None
        if chunk.thema_id:
            thema = await db.get(models.Thema, chunk.thema_id)
            thema_titel = thema.titel if thema else None

        tage = (heute - chunk.quelldatum.replace(tzinfo=timezone.utc if chunk.quelldatum.tzinfo is None else chunk.quelldatum.tzinfo)).days

        items.append(VeraltetItem(
            chunk_id=chunk.id,
            thema_id=chunk.thema_id,
            thema_titel=thema_titel,
            quelldatum=chunk.quelldatum.date().isoformat(),
            veraltet_seit_tagen=max(0, tage - VERALTET_SCHWELLE_TAGE),
            vorschlag="Thema neu einlesen aus SharePoint oder Upload",
        ).model_dump())

    return {"items": items, "total": len(items)}


async def markiere_veraltete_chunks(db: AsyncSession) -> int:
    """Setzt ist_veraltet=True für alle Chunks älter als Schwelle. Gibt Anzahl zurück."""
    schwelle = datetime.now(timezone.utc) - timedelta(days=VERALTET_SCHWELLE_TAGE)
    rows = await db.scalars(
        select(models.Chunk).where(
            models.Chunk.quelldatum < schwelle,
            models.Chunk.ist_veraltet.is_(False),
        )
    )
    count = 0
    for chunk in rows:
        chunk.ist_veraltet = True
        count += 1
    if count:
        await db.commit()
    return count
