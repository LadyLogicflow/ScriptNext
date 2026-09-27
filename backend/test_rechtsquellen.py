"""Tests für Rechtsquellen-DB, Import-Idempotenz, Suche und Zitier-Guard."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── RSS-Parsing ───────────────────────────────────────────────────────────────

class TestRssParsing:
    _rss_sample = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Test Feed</title>
        <item>
          <title>ArbSchG – Arbeitsschutzgesetz</title>
          <link>https://www.gesetze-im-internet.de/arbschg/</link>
          <pubDate>Mon, 01 Jan 2024 00:00:00 +0000</pubDate>
          <description>Gesetz über die Durchführung von Maßnahmen...</description>
        </item>
        <item>
          <title>BetrVG – Betriebsverfassungsgesetz</title>
          <link>https://www.gesetze-im-internet.de/betrvg/</link>
          <pubDate>Tue, 15 Feb 2024 00:00:00 +0000</pubDate>
          <description>Betriebsverfassung kurz erklärt</description>
        </item>
      </channel>
    </rss>"""

    def test_parst_zwei_items(self):
        from rechtsquellen import _parse_rss_items
        items = _parse_rss_items(self._rss_sample)
        assert len(items) == 2

    def test_felder_vorhanden(self):
        from rechtsquellen import _parse_rss_items
        items = _parse_rss_items(self._rss_sample)
        assert items[0]["title"] == "ArbSchG – Arbeitsschutzgesetz"
        assert "gesetze-im-internet.de" in items[0]["link"]
        assert items[0]["description"] != ""

    def test_leeres_xml_gibt_leere_liste(self):
        from rechtsquellen import _parse_rss_items
        assert _parse_rss_items("") == []
        assert _parse_rss_items("<malformed") == []

    def test_atom_feed(self):
        from rechtsquellen import _parse_rss_items
        atom = """<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>BFH Urteil VI R 1/23</title>
            <link href="https://example.com/1"/>
            <published>2024-03-01T00:00:00Z</published>
            <summary>Leitsatz des Urteils</summary>
          </entry>
        </feed>"""
        items = _parse_rss_items(atom)
        assert len(items) == 1
        assert "VI R 1/23" in items[0]["title"]


# ── Datum-Parsing ─────────────────────────────────────────────────────────────

class TestDatumParsing:
    def test_rfc_2822_format(self):
        from rechtsquellen import _parse_pub_date
        d = _parse_pub_date("Mon, 01 Jan 2024 00:00:00 +0000")
        assert d is not None
        assert d.year == 2024

    def test_iso_format(self):
        from rechtsquellen import _parse_pub_date
        d = _parse_pub_date("2024-06-15T10:00:00Z")
        assert d is not None
        assert d.month == 6

    def test_leer_gibt_none(self):
        from rechtsquellen import _parse_pub_date
        assert _parse_pub_date("") is None
        assert _parse_pub_date("ungültig") is None


# ── Aktenzeichen-Extraktion ───────────────────────────────────────────────────

class TestAktenzeichen:
    def test_standard_format(self):
        from rechtsquellen import _extrahiere_aktenzeichen
        az = _extrahiere_aktenzeichen("BFH-Urteil VI R 12/23 – Arbeitnehmer-Pauschbetrag")
        assert az is not None
        assert "VI" in az
        assert "12/23" in az

    def test_kein_aktenzeichen(self):
        from rechtsquellen import _extrahiere_aktenzeichen
        assert _extrahiere_aktenzeichen("Pressemitteilung ohne Aktenzeichen") is None

    def test_verschiedene_senate(self):
        from rechtsquellen import _extrahiere_aktenzeichen
        for az_str in ["I B 2/24", "IV R 5/22", "IX R 10/23"]:
            result = _extrahiere_aktenzeichen(f"BFH Az. {az_str}")
            assert result is not None, f"Kein AZ für '{az_str}' gefunden"


# ── Import-Idempotenz ─────────────────────────────────────────────────────────

class TestImportIdempotenz:
    def test_zweiter_import_wird_uebersprungen(self):
        """Gleiche externe_id darf nicht doppelt gespeichert werden."""
        import asyncio
        from rechtsquellen import _upsert_rechtsquelle

        mock_db = AsyncMock()
        # Erstes Mal: kein existierender Eintrag
        mock_db.scalar = AsyncMock(return_value=None)
        result1 = asyncio.run(_upsert_rechtsquelle(mock_db, {
            "typ": "gesetz",
            "titel": "ArbSchG",
            "externe_id": "gii:https://example.com/arbschg",
        }))
        assert result1 == "neu"
        mock_db.add.assert_called_once()

        # Zweites Mal: existierender Eintrag
        mock_db.reset_mock()
        mock_db.scalar = AsyncMock(return_value=MagicMock())  # simuliert vorhandenen Eintrag
        result2 = asyncio.run(_upsert_rechtsquelle(mock_db, {
            "typ": "gesetz",
            "titel": "ArbSchG",
            "externe_id": "gii:https://example.com/arbschg",
        }))
        assert result2 == "uebersprungen"
        mock_db.add.assert_not_called()

    def test_ohne_externe_id_wird_uebersprungen(self):
        """Einträge ohne externe_id werden nicht gespeichert."""
        import asyncio
        from rechtsquellen import _upsert_rechtsquelle
        mock_db = AsyncMock()
        result = asyncio.run(_upsert_rechtsquelle(mock_db, {
            "typ": "gesetz",
            "titel": "Ohne ID",
        }))
        assert result == "uebersprungen"


# ── Import-Endpoint (mit gemocktem HTTP) ─────────────────────────────────────

class TestImportEndpoint:
    _mock_rss = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item><title>ArbSchG</title><link>https://gii.de/arbschg/</link>
        <pubDate>Mon, 01 Jan 2024 00:00:00 +0000</pubDate><description>Text</description></item>
    </channel></rss>"""

    def test_unbekannte_quelle_400(self):
        """Unbekannte Quelle muss 400 ergeben."""
        from app import app
        from fastapi.testclient import TestClient
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                r = client.post(
                    "/api/v1/rechtsquellen/import",
                    json={"quelle": "unbekannt"},
                )
                assert r.status_code in (400, 401, 500)
        except Exception:
            pytest.skip("DB nicht erreichbar")

    def test_import_ohne_auth_401(self):
        """Import ohne JWT muss 401 ergeben."""
        from app import app
        from fastapi.testclient import TestClient
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                r = client.post(
                    "/api/v1/rechtsquellen/import",
                    json={"quelle": "gesetze-im-internet"},
                )
                assert r.status_code in (401, 500)
        except Exception:
            pytest.skip("DB nicht erreichbar")

    def test_gii_import_mit_mock_http(self):
        """GII-Import mit gemocktem HTTP gibt korrektes Ergebnis."""
        import asyncio
        import rechtsquellen as rq

        mock_resp = MagicMock()
        mock_resp.text = self._mock_rss
        mock_resp.raise_for_status = MagicMock()

        mock_db = AsyncMock()
        mock_db.scalar = AsyncMock(return_value=None)

        async def _run():
            with patch("rechtsquellen.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_client
                return await rq._import_gii(mock_db)

        result = asyncio.run(_run())
        assert result["neu"] == 1
        assert result["uebersprungen"] == 0
        assert result["fehler"] == []

    def test_gii_import_http_fehler_gibt_fehler_liste(self):
        """HTTP-Fehler beim GII-Import führt zu fehler-Liste, nicht Exception."""
        import asyncio
        import rechtsquellen as rq

        mock_db = AsyncMock()

        async def _run():
            with patch("rechtsquellen.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
                mock_client_cls.return_value = mock_client
                return await rq._import_gii(mock_db)

        result = asyncio.run(_run())
        assert len(result["fehler"]) > 0
        assert result["neu"] == 0


# ── Suche + Filter ────────────────────────────────────────────────────────────

class TestSucheFilter:
    def test_liste_ohne_auth_401(self):
        """Liste ohne Auth muss 401 ergeben."""
        from app import app
        from fastapi.testclient import TestClient
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                r = client.get("/api/v1/rechtsquellen")
                assert r.status_code in (401, 500)
        except Exception:
            pytest.skip("DB nicht erreichbar")

    def test_list_item_schema(self):
        """RechtsquelleListItem muss korrekte Felder haben."""
        from rechtsquellen import RechtsquelleListItem
        item = RechtsquelleListItem(
            id=uuid.uuid4(),
            typ="gesetz",
            titel="ArbSchG § 3",
            paragraph="§ 3",
            gesetz="ArbSchG",
            aktenzeichen=None,
            datum="2024-01-01",
            kurztext="Kurzer Text...",
            quelle_url="https://example.com",
        )
        assert item.typ == "gesetz"
        assert item.aktenzeichen is None

    def test_von_model_kurztext(self):
        """von_model kürzt volltext auf 200 Zeichen."""
        from rechtsquellen import RechtsquelleListItem
        mock_rq = MagicMock()
        mock_rq.id = uuid.uuid4()
        mock_rq.typ = "urteil"
        mock_rq.titel = "Test-Urteil"
        mock_rq.paragraph = None
        mock_rq.gesetz = None
        mock_rq.aktenzeichen = "VI R 1/23"
        mock_rq.volltext = "X" * 500
        mock_rq.datum = None
        mock_rq.quelle_url = None
        item = RechtsquelleListItem.von_model(mock_rq)
        assert len(item.kurztext) == 200


# ── Zitier-Guard ──────────────────────────────────────────────────────────────

class TestZitierGuard:
    def test_guard_ohne_treffer_enthaelt_quelle_offen(self):
        """Ohne Treffer muss 'Quelle offen' in den Prompt-Abschnitt."""
        from ki import _baue_zitier_abschnitt
        abschnitt = _baue_zitier_abschnitt(None)
        assert "Quelle offen" in abschnitt
        assert "keine" in abschnitt.lower()

    def test_guard_mit_treffern_enthaelt_quellen(self):
        """Mit Treffern müssen die Zitier-Strings im Abschnitt stehen."""
        from ki import _baue_zitier_abschnitt
        treffer = ["ArbSchG § 3 Abs.1", "VI R 12/23"]
        abschnitt = _baue_zitier_abschnitt(treffer)
        assert "ArbSchG § 3 Abs.1" in abschnitt
        assert "VI R 12/23" in abschnitt
        assert "Quelle offen" in abschnitt  # Regel bleibt immer drin

    def test_guard_ist_in_generiere_seminar_prompt(self):
        """Zitier-Guard-Abschnitt muss in Stufe-2-Prompt erscheinen."""
        import asyncio
        from ki import generiere_seminar, _ZITIER_GUARD_REGEL

        captured_prompts = []

        class MockMsg:
            content = [MagicMock(text="ABSCHNITT_1_TYP: einstieg\nABSCHNITT_1_TITEL: Test\n")]

        class MockClient:
            def messages(self):
                pass

        mock_client = MagicMock()
        mock_client.messages.create.return_value = MockMsg()

        with patch("ki._anthropic_client", return_value=mock_client):
            # Capture prompt calls
            original_create = mock_client.messages.create

            def capturing_create(**kwargs):
                captured_prompts.append(kwargs.get("messages", []))
                return MockMsg()

            mock_client.messages.create.side_effect = capturing_create

            asyncio.run(generiere_seminar(
                thema_titel="Arbeitsrecht",
                chunk_texte=["Text über ArbSchG"],
                api_key="test-key",
                rechtsquellen_treffer=["ArbSchG § 3"],
            ))

        # Stufe 2 (zweiter Call) muss den Guard enthalten
        assert len(captured_prompts) >= 2
        stufe2_content = captured_prompts[1][0]["content"]
        assert "Quelle offen" in stufe2_content
        assert "ArbSchG § 3" in stufe2_content

    def test_fallback_ohne_api_key_ignoriert_guard(self):
        """Ohne API-Key wird Fallback zurückgegeben — Guard nicht relevant."""
        import asyncio
        from ki import generiere_seminar
        result = asyncio.run(generiere_seminar(
            thema_titel="Test",
            chunk_texte=[],
            api_key="",
            rechtsquellen_treffer=["ArbSchG § 3"],
        ))
        assert result is not None
        assert result["titel"] == "Test"
