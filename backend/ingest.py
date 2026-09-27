"""PDF-Ingest-Pipeline: Extraktion → Chunking → Embedding."""
import io
import logging
import re
import uuid
from pathlib import Path
from typing import Generator

logger = logging.getLogger(__name__)

# pdfplumber für normale PDFs
try:
    import pdfplumber
    PDFPLUMBER_OK = True
except ImportError:
    PDFPLUMBER_OK = False

# OCR-Fallback für Scan-PDFs
try:
    import pytesseract
    from pdf2image import convert_from_bytes
    OCR_OK = True
except ImportError:
    OCR_OK = False


def extrahiere_text(pdf_bytes: bytes) -> list[tuple[int, str]]:
    """Gibt Liste von (seitennummer_1basiert, text) zurück."""
    seiten: list[tuple[int, str]] = []

    if PDFPLUMBER_OK:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, seite in enumerate(pdf.pages, 1):
                text = seite.extract_text() or ""
                seiten.append((i, text.strip()))

    # Prüfe ob OCR nötig (leere Seiten = wahrscheinlich Scan)
    leere = [s for _, s in seiten if len(s) < 50]
    if len(leere) > len(seiten) * 0.5 and OCR_OK:
        logger.info("Mehr als 50%% leere Seiten — versuche OCR-Fallback")
        seiten = _ocr_extraktion(pdf_bytes)

    return seiten


def _ocr_extraktion(pdf_bytes: bytes) -> list[tuple[int, str]]:
    """Tesseract-OCR für Scan-PDFs."""
    seiten = []
    try:
        bilder = convert_from_bytes(pdf_bytes, dpi=200)
        for i, bild in enumerate(bilder, 1):
            text = pytesseract.image_to_string(bild, lang="deu+eng")
            seiten.append((i, text.strip()))
    except Exception as e:
        logger.error("OCR-Fehler: %s", e)
    return seiten


def erstelle_chunks(
    seiten: list[tuple[int, str]],
    chunk_groesse: int = 500,
    overlap: int = 50,
) -> Generator[dict, None, None]:
    """
    Gibt Chunk-Dicts zurück: {text, seite, chunk_index}.
    Chunking: nach Wörtern, mit Overlap.
    """
    # Gesamttext mit Seitenmarkierungen aufbauen
    woerter_mit_seite: list[tuple[str, int]] = []
    for seite_nr, text in seiten:
        for wort in text.split():
            woerter_mit_seite.append((wort, seite_nr))

    if not woerter_mit_seite:
        return

    schritt = chunk_groesse - overlap
    idx = 0
    chunk_nr = 0

    while idx < len(woerter_mit_seite):
        ende = min(idx + chunk_groesse, len(woerter_mit_seite))
        chunk_woerter = woerter_mit_seite[idx:ende]

        text = " ".join(w for w, _ in chunk_woerter)
        text = _bereinige_text(text)

        if len(text) > 20:
            # Seite = die Seite des ersten Worts im Chunk
            seite = chunk_woerter[0][1]
            yield {"text": text, "seite": seite, "chunk_index": chunk_nr}
            chunk_nr += 1

        idx += schritt


def _bereinige_text(text: str) -> str:
    """Entfernt übermäßige Leerzeichen und Steuerzeichen."""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r" {3,}", "  ", text)
    return text.strip()


async def erstelle_embedding(text: str, api_key: str, model: str = "text-embedding-3-small") -> list[float] | None:
    """Ruft OpenAI-Embeddings ab. Gibt None zurück wenn kein API-Key konfiguriert."""
    if not api_key:
        return None
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)
        response = await client.embeddings.create(model=model, input=text[:8000])
        return response.data[0].embedding
    except Exception as e:
        logger.warning("Embedding-Fehler: %s", e)
        return None


def erkenne_themen(chunks: list[dict]) -> list[dict]:
    """
    Einfache heuristische Themen-Erkennung für MVP:
    Gruppiert nach Überschriften (Zeilen mit < 80 Zeichen am Chunk-Anfang).
    In Sprint 2 durch KI-Clustering ersetzt.
    """
    themen: list[dict] = []
    aktuelles_thema: dict | None = None

    for chunk in chunks:
        text = chunk["text"]
        erste_zeile = text.split("\n")[0].strip()

        ist_ueberschrift = (
            len(erste_zeile) < 80
            and len(erste_zeile) > 3
            and not erste_zeile.endswith(".")
            and erste_zeile[0].isupper()
        )

        if ist_ueberschrift or aktuelles_thema is None:
            if aktuelles_thema:
                themen.append(aktuelles_thema)
            aktuelles_thema = {
                "id": str(uuid.uuid4()),
                "titel": erste_zeile[:200],
                "beschreibung": f"Seite {chunk['seite']}",
                "chunk_ids": [chunk.get("id")],
            }
        else:
            aktuelles_thema["chunk_ids"].append(chunk.get("id"))

    if aktuelles_thema:
        themen.append(aktuelles_thema)

    return themen if themen else [{"id": str(uuid.uuid4()), "titel": "Inhalt", "beschreibung": None, "chunk_ids": [c.get("id") for c in chunks]}]
