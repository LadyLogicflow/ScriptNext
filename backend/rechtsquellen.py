"""Rechtsquellen-DB: Import-Skripte (GII/BFH/BMF) + REST-Endpoints."""
import logging
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Annotated
from xml.etree import ElementTree as ET

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import TokenPayload, aktueller_nutzer
from database import get_db
import models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rechtsquellen", tags=["rechtsquellen"])

# ── Quellen-URLs ─────────────────────────────────────────────────────────────

GII_RSS_URL = "https://www.gesetze-im-internet.de/rss.xml"
BFH_RSS_URL = "https://www.bundesfinanzhof.de/de/entscheidungen/entscheidungen-online/?tx_bfhentscheidungen_pi1%5Baction%5D=rss&tx_bfhentscheidungen_pi1%5Bcontroller%5D=Entscheidung&cHash=abc"
BFH_PM_URL = "https://www.bundesfinanzhof.de/rss/pm.xml"
BMF_RSS_URL = "https://www.bundesfinanzministerium.de/SiteGlobals/Functions/RSSFeed/DE/RSSNewsfeed/XML_Schreiben.xml"

QUELLEN = ("gesetze-im-internet", "bfh", "bmf")

# ── Schemas ───────────────────────────────────────────────────────────────────

from pydantic import BaseModel


class ImportRequest(BaseModel):
    quelle: str  # "gesetze-im-internet" | "bfh" | "bmf"


class RechtsquelleListItem(BaseModel):
    id: uuid.UUID
    typ: str
    titel: str
    paragraph: str | None
    gesetz: str | None
    aktenzeichen: str | None
    datum: str | None
    kurztext: str | None
    quelle_url: str | None

    @classmethod
    def von_model(cls, r: models.Rechtsquelle) -> "RechtsquelleListItem":
        kurztext = (r.volltext or "")[:200] or None
        return cls(
            id=r.id,
            typ=r.typ,
            titel=r.titel,
            paragraph=r.paragraph,
            gesetz=r.gesetz,
            aktenzeichen=r.aktenzeichen,
            datum=r.datum.date().isoformat() if r.datum else None,
            kurztext=kurztext,
            quelle_url=r.quelle_url,
        )


class RechtsquelleDetail(RechtsquelleListItem):
    volltext: str | None
    fundstelle: str | None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/import", tags=["rechtsquellen"])
async def rechtsquellen_import(
    payload: ImportRequest,
    token_data: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Importiert Rechtsquellen aus einer externen Quelle. Idempotent."""
    if payload.quelle not in QUELLEN:
        raise HTTPException(status_code=400, detail=f"Unbekannte Quelle. Erlaubt: {', '.join(QUELLEN)}")

    if payload.quelle == "gesetze-im-internet":
        result = await _import_gii(db)
    elif payload.quelle == "bfh":
        result = await _import_bfh(db)
    else:
        result = await _import_bmf(db)

    return result


@router.get("", tags=["rechtsquellen"])
async def rechtsquellen_liste(
    token_data: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
    typ: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """Listet Rechtsquellen mit optionalem Typ-Filter und Volltext-Suche."""
    if limit > 200:
        limit = 200
    stmt = select(models.Rechtsquelle)
    if typ and typ in ("gesetz", "urteil", "schreiben"):
        stmt = stmt.where(models.Rechtsquelle.typ == typ)
    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                models.Rechtsquelle.titel.ilike(term),
                models.Rechtsquelle.volltext.ilike(term),
                models.Rechtsquelle.aktenzeichen.ilike(term),
                models.Rechtsquelle.gesetz.ilike(term),
            )
        )
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(count_stmt) or 0
    rows = await db.scalars(stmt.order_by(models.Rechtsquelle.datum.desc().nullslast()).offset(offset).limit(limit))
    items = [RechtsquelleListItem.von_model(r) for r in rows]
    return {"items": [i.model_dump() for i in items], "total": total}


@router.get("/{rechtsquelle_id}", tags=["rechtsquellen"])
async def rechtsquelle_detail(
    rechtsquelle_id: uuid.UUID,
    token_data: Annotated[TokenPayload, Depends(aktueller_nutzer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Gibt eine Rechtsquelle mit Volltext zurück."""
    row = await db.get(models.Rechtsquelle, rechtsquelle_id)
    if not row:
        raise HTTPException(status_code=404, detail="Rechtsquelle nicht gefunden")
    base = RechtsquelleListItem.von_model(row)
    return RechtsquelleDetail(
        **base.model_dump(),
        volltext=row.volltext,
        fundstelle=row.fundstelle,
    ).model_dump()


# ── Import-Logik ──────────────────────────────────────────────────────────────

async def _upsert_rechtsquelle(db: AsyncSession, data: dict) -> str:
    """Speichert eine Rechtsquelle idempotent. Gibt 'neu'|'uebersprungen' zurück."""
    externe_id = data.get("externe_id")
    if not externe_id:
        return "uebersprungen"

    existing = await db.scalar(
        select(models.Rechtsquelle).where(models.Rechtsquelle.externe_id == externe_id)
    )
    if existing:
        return "uebersprungen"

    db.add(models.Rechtsquelle(
        typ=data["typ"],
        titel=data["titel"],
        paragraph=data.get("paragraph"),
        gesetz=data.get("gesetz"),
        aktenzeichen=data.get("aktenzeichen"),
        volltext=data.get("volltext"),
        quelle_url=data.get("quelle_url"),
        datum=data.get("datum"),
        fundstelle=data.get("fundstelle"),
        externe_id=externe_id,
    ))
    return "neu"


def _parse_rss_items(xml_text: str) -> list[dict]:
    """Parst RSS 2.0 oder Atom-Feed. Gibt Liste von {title, link, pubDate, description} zurück."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    ns = {}
    items = []

    # RSS 2.0
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        desc = (item.findtext("description") or "").strip()
        if title:
            items.append({"title": title, "link": link, "pubDate": pub, "description": desc})

    # Atom
    if not items:
        atom_ns = "http://www.w3.org/2005/Atom"
        for entry in root.iter(f"{{{atom_ns}}}entry"):
            title = (entry.findtext(f"{{{atom_ns}}}title") or "").strip()
            link_el = entry.find(f"{{{atom_ns}}}link")
            link = link_el.get("href", "") if link_el is not None else ""
            pub = (entry.findtext(f"{{{atom_ns}}}published") or entry.findtext(f"{{{atom_ns}}}updated") or "").strip()
            desc = (entry.findtext(f"{{{atom_ns}}}summary") or entry.findtext(f"{{{atom_ns}}}content") or "").strip()
            if title:
                items.append({"title": title, "link": link, "pubDate": pub, "description": desc})

    return items


def _parse_pub_date(date_str: str) -> datetime | None:
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str).astimezone(timezone.utc)
    except Exception:
        pass
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        return None


async def _import_gii(db: AsyncSession) -> dict:
    """Importiert Gesetze aus dem gesetze-im-internet.de RSS-Feed."""
    neu = uebersprungen = 0
    fehler: list[str] = []

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(GII_RSS_URL, headers={"User-Agent": "ScriptNext/1.0"})
            r.raise_for_status()
            rss_items = _parse_rss_items(r.text)
    except Exception as e:
        logger.warning("GII-Import: HTTP-Fehler: %s", e)
        return {"neu": 0, "uebersprungen": 0, "fehler": [f"HTTP: {type(e).__name__}"]}

    for item in rss_items:
        titel = item["title"]
        link = item["link"]
        externe_id = f"gii:{link or titel[:200]}"
        # Gesetzesabkürzung aus Titel extrahieren (häufig "Kürzel – Vollname")
        gesetz = titel.split("–")[0].strip().split(" ")[0] if "–" in titel else titel[:50]

        status_r = await _upsert_rechtsquelle(db, {
            "typ": "gesetz",
            "titel": titel,
            "gesetz": gesetz,
            "quelle_url": link,
            "volltext": item["description"],
            "datum": _parse_pub_date(item["pubDate"]),
            "externe_id": externe_id,
        })
        if status_r == "neu":
            neu += 1
        else:
            uebersprungen += 1

    await db.commit()
    return {"neu": neu, "uebersprungen": uebersprungen, "fehler": fehler}


async def _import_bfh(db: AsyncSession) -> dict:
    """Importiert BFH-Pressemitteilungen (Urteile) via RSS."""
    neu = uebersprungen = 0
    fehler: list[str] = []

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(BFH_PM_URL, headers={"User-Agent": "ScriptNext/1.0"})
            r.raise_for_status()
            rss_items = _parse_rss_items(r.text)
    except Exception as e:
        logger.warning("BFH-Import: HTTP-Fehler: %s", e)
        return {"neu": 0, "uebersprungen": 0, "fehler": [f"HTTP: {type(e).__name__}"]}

    for item in rss_items:
        titel = item["title"]
        link = item["link"]
        desc = item["description"]

        # Aktenzeichen aus Titel extrahieren (Format: "PM Nr. XX/YY – Az. X R 1/23")
        aktenzeichen = _extrahiere_aktenzeichen(titel + " " + desc)
        externe_id = f"bfh:{aktenzeichen or link or titel[:200]}"

        status_r = await _upsert_rechtsquelle(db, {
            "typ": "urteil",
            "titel": titel,
            "aktenzeichen": aktenzeichen,
            "volltext": desc,
            "quelle_url": link,
            "datum": _parse_pub_date(item["pubDate"]),
            "externe_id": externe_id,
        })
        if status_r == "neu":
            neu += 1
        else:
            uebersprungen += 1

    await db.commit()
    return {"neu": neu, "uebersprungen": uebersprungen, "fehler": fehler}


async def _import_bmf(db: AsyncSession) -> dict:
    """Importiert BMF-Schreiben via RSS-Feed."""
    neu = uebersprungen = 0
    fehler: list[str] = []

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(BMF_RSS_URL, headers={"User-Agent": "ScriptNext/1.0"})
            r.raise_for_status()
            rss_items = _parse_rss_items(r.text)
    except Exception as e:
        logger.warning("BMF-Import: HTTP-Fehler: %s", e)
        return {"neu": 0, "uebersprungen": 0, "fehler": [f"HTTP: {type(e).__name__}"]}

    for item in rss_items:
        titel = item["title"]
        link = item["link"]
        externe_id = f"bmf:{link or titel[:200]}"

        status_r = await _upsert_rechtsquelle(db, {
            "typ": "schreiben",
            "titel": titel,
            "volltext": item["description"],
            "quelle_url": link,
            "datum": _parse_pub_date(item["pubDate"]),
            "externe_id": externe_id,
        })
        if status_r == "neu":
            neu += 1
        else:
            uebersprungen += 1

    await db.commit()
    return {"neu": neu, "uebersprungen": uebersprungen, "fehler": fehler}


def _extrahiere_aktenzeichen(text: str) -> str | None:
    """Extrahiert BFH-Aktenzeichen aus Freitext (z.B. 'VI R 1/23', 'I B 2/24')."""
    import re
    # BFH-Format: I-XVI + optional B/R + Ziffer / Jahr
    m = re.search(r'\b([IVX]{1,4}(?:\s+[BR]|\s+[A-Z]R?)?)\s+(\d+)/(\d{2,4})\b', text)
    if m:
        return m.group(0).strip()
    return None


async def suche_rechtsquellen_fuer_thema(thema_text: str, db: AsyncSession, limit: int = 5) -> list[str]:
    """Sucht passende Rechtsquellen für einen Thema-Text. Gibt Zitier-Strings zurück."""
    woerter = [w for w in thema_text.split() if len(w) > 4][:10]
    if not woerter:
        return []

    treffer = []
    for wort in woerter[:3]:
        rows = await db.scalars(
            select(models.Rechtsquelle)
            .where(
                or_(
                    models.Rechtsquelle.titel.ilike(f"%{wort}%"),
                    models.Rechtsquelle.gesetz.ilike(f"%{wort}%"),
                )
            )
            .limit(limit)
        )
        for r in rows:
            zitat = r.aktenzeichen or (f"{r.gesetz} {r.paragraph}".strip() if r.gesetz else r.titel[:80])
            if zitat and zitat not in treffer:
                treffer.append(zitat)

    return treffer[:limit]
