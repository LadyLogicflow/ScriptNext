"""Zwei-Stufen-KI-Pipeline für ScriptNext (Anthropic Claude)."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"


def _anthropic_client(api_key: str):
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


_ZITIER_GUARD_REGEL = (
    "WICHTIG – Zitier-Guard: Nenne Aktenzeichen oder Paragrafen NUR dann explizit, "
    "wenn sie in der unten stehenden Liste verifizierter Rechtsquellen erscheinen. "
    "Fehlt eine Quelle in der Liste, schreibe stattdessen 'Quelle offen'. "
    "Erfundene Aktenzeichen oder Paragrafen sind verboten."
)


async def generiere_seminar(
    thema_titel: str,
    chunk_texte: list[str],
    zielgruppe: str = "Mitarbeitende",
    dauer_minuten: int = 90,
    api_key: str = "",
    rechtsquellen_treffer: list[str] | None = None,
) -> Optional[dict]:
    """Zwei-Stufen-Pipeline: Lernziele → Seminarstruktur mit W-Fragen.

    rechtsquellen_treffer: verifizierte Zitier-Strings aus der Rechtsquellen-DB.
    Wenn übergeben, wird der Zitier-Guard in den Prompt eingebaut.
    """
    if not api_key:
        return _seminar_fallback(thema_titel, zielgruppe, dauer_minuten)

    kontext = "\n\n".join(chunk_texte[:8])  # max 8 Chunks
    zitier_abschnitt = _baue_zitier_abschnitt(rechtsquellen_treffer)

    try:
        client = _anthropic_client(api_key)

        # Stufe 1: Lernziele extrahieren
        stufe1 = client.messages.create(
            model=_ANTHROPIC_MODEL,
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": (
                    f"Analysiere den folgenden Text zum Thema '{thema_titel}' "
                    f"und formuliere 3-5 konkrete Lernziele für {zielgruppe}. "
                    f"Antworte NUR mit einer nummerierten Liste.\n\nText:\n{kontext}"
                ),
            }],
        )
        lernziele_text = stufe1.content[0].text.strip()

        # Stufe 2: Seminarstruktur mit W-Fragen + Zitier-Guard
        stufe2 = client.messages.create(
            model=_ANTHROPIC_MODEL,
            max_tokens=1500,
            messages=[{
                "role": "user",
                "content": (
                    f"Erstelle eine Seminarstruktur für '{thema_titel}' ({dauer_minuten} Min, {zielgruppe}).\n"
                    f"Lernziele:\n{lernziele_text}\n\n"
                    f"{zitier_abschnitt}"
                    f"Gib exakt 4 Abschnitte zurück im Format:\n"
                    f"ABSCHNITT_1_TYP: einstieg\n"
                    f"ABSCHNITT_1_TITEL: ...\n"
                    f"ABSCHNITT_1_INHALT: ...\n"
                    f"ABSCHNITT_1_WFRAGE: Was bedeutet ... für die Praxis?\n"
                    f"ABSCHNITT_1_DAUER: 10\n"
                    f"[analog für 2, 3, 4 mit typen: inhalt, uebung, abschluss]"
                ),
            }],
        )
        struktur_text = stufe2.content[0].text.strip()

        abschnitte = _parse_abschnitte(struktur_text)
        return {
            "titel": thema_titel,
            "zielgruppe": zielgruppe,
            "dauer_minuten": dauer_minuten,
            "lernziele": lernziele_text,
            "abschnitte": abschnitte,
        }

    except Exception as exc:
        logger.warning("KI-Fehler: %s — nutze Fallback", exc)
        return _seminar_fallback(thema_titel, zielgruppe, dauer_minuten)


def _baue_zitier_abschnitt(treffer: list[str] | None) -> str:
    """Erstellt den Zitier-Guard-Abschnitt für den KI-Prompt."""
    if not treffer:
        return (
            f"{_ZITIER_GUARD_REGEL}\n"
            f"Verifizierte Rechtsquellen: (keine – schreibe 'Quelle offen' bei Referenzen)\n\n"
        )
    quellen_liste = "\n".join(f"  – {t}" for t in treffer)
    return (
        f"{_ZITIER_GUARD_REGEL}\n"
        f"Verifizierte Rechtsquellen für dieses Thema:\n{quellen_liste}\n\n"
    )


def _parse_abschnitte(text: str) -> list[dict]:
    """Parst die strukturierte KI-Antwort in Abschnitt-Dictionaries."""
    abschnitte = []
    for i in range(1, 5):
        prefix = f"ABSCHNITT_{i}_"
        ab = {}
        for zeile in text.splitlines():
            for key in ("TYP", "TITEL", "INHALT", "WFRAGE", "DAUER"):
                marker = f"{prefix}{key}:"
                if zeile.strip().startswith(marker):
                    ab[key.lower()] = zeile.split(":", 1)[1].strip()
        if ab.get("titel"):
            abschnitte.append({
                "reihenfolge": i,
                "typ": ab.get("typ", "inhalt"),
                "titel": ab.get("titel", f"Abschnitt {i}"),
                "inhalt": ab.get("inhalt"),
                "w_frage": ab.get("wfrage"),
                "dauer_minuten": int(ab["dauer"]) if ab.get("dauer", "").isdigit() else None,
            })
    # Fallback: immer 4 Abschnitte zurückgeben
    while len(abschnitte) < 4:
        typen = ["einstieg", "inhalt", "uebung", "abschluss"]
        i = len(abschnitte) + 1
        abschnitte.append({
            "reihenfolge": i,
            "typ": typen[i - 1] if i <= 4 else "inhalt",
            "titel": f"Abschnitt {i}",
            "inhalt": None,
            "w_frage": None,
            "dauer_minuten": None,
        })
    return abschnitte[:4]


def _seminar_fallback(thema_titel: str, zielgruppe: str, dauer_minuten: int) -> dict:
    """Gibt eine Basis-Seminarstruktur zurück wenn keine KI verfügbar."""
    return {
        "titel": thema_titel,
        "zielgruppe": zielgruppe,
        "dauer_minuten": dauer_minuten,
        "lernziele": f"Lernziele für {thema_titel} (bitte KI-API-Key konfigurieren)",
        "abschnitte": [
            {"reihenfolge": 1, "typ": "einstieg", "titel": "Einstieg & Begrüßung",
             "inhalt": f"Einführung in {thema_titel}", "w_frage": f"Was wissen Sie bereits über {thema_titel}?",
             "dauer_minuten": max(5, dauer_minuten // 10)},
            {"reihenfolge": 2, "typ": "inhalt", "titel": f"Grundlagen: {thema_titel}",
             "inhalt": "Fachliche Inhalte", "w_frage": f"Wie ist {thema_titel} in der Praxis umgesetzt?",
             "dauer_minuten": dauer_minuten // 2},
            {"reihenfolge": 3, "typ": "uebung", "titel": "Übung & Praxisanwendung",
             "inhalt": "Gruppenarbeit / Fallbeispiele", "w_frage": f"Warum ist {thema_titel} relevant?",
             "dauer_minuten": dauer_minuten // 4},
            {"reihenfolge": 4, "typ": "abschluss", "titel": "Zusammenfassung & Ausblick",
             "inhalt": "Kernaussagen & nächste Schritte", "w_frage": f"Welche Maßnahmen leiten Sie ab?",
             "dauer_minuten": max(5, dauer_minuten // 10)},
        ],
    }
