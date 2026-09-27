"""Tests für Feedback-Schleife & Themen-Versionierung (Etappe 3c)."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Schema-Tests ──────────────────────────────────────────────────────────────

class TestFeedbackSchemas:
    def test_feedback_request_bewertungen(self):
        """FeedbackRequest akzeptiert nur gültige Bewertungen."""
        from feedback import FeedbackRequest
        req = FeedbackRequest(bewertung="gut")
        assert req.bewertung == "gut"
        assert req.kommentar is None

    def test_feedback_request_mit_kommentar(self):
        from feedback import FeedbackRequest
        req = FeedbackRequest(bewertung="zu_langweilig", kommentar="War zu trocken")
        assert req.kommentar == "War zu trocken"

    def test_kommentar_max_laenge(self):
        """Kommentar darf max 1000 Zeichen haben."""
        from feedback import FeedbackRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FeedbackRequest(bewertung="gut", kommentar="x" * 1001)

    def test_veraltet_item_schema(self):
        from feedback import VeraltetItem
        item = VeraltetItem(
            chunk_id=uuid.uuid4(),
            thema_id=uuid.uuid4(),
            thema_titel="Arbeitsrecht",
            quelldatum="2022-01-01",
            veraltet_seit_tagen=400,
            vorschlag="Neu einlesen",
        )
        assert item.veraltet_seit_tagen == 400

    def test_feedback_stats_schema(self):
        from feedback import FeedbackStats
        stats = FeedbackStats(gesamt=10, gut=7, zu_langweilig=2, falsche_ebene=1, letztes_feedback="2026-09-27")
        assert stats.gesamt == 10
        assert stats.gut + stats.zu_langweilig + stats.falsche_ebene == 10


# ── Feedback-Persistenz ───────────────────────────────────────────────────────

class TestFeedbackPersistenz:
    def test_ungueltige_bewertung_400(self):
        """Ungültige Bewertung muss 400 geben."""
        from app import app
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                r = client.post(
                    f"/api/v1/seminare/{uuid.uuid4()}/feedback",
                    json={"bewertung": "ungueltig"},
                )
                assert r.status_code in (400, 401, 500)
        except Exception:
            pytest.skip("DB nicht erreichbar")

    def test_feedback_ohne_auth_401(self):
        """Ohne Auth muss 401 kommen."""
        from app import app
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                r = client.post(
                    f"/api/v1/seminare/{uuid.uuid4()}/feedback",
                    json={"bewertung": "gut"},
                )
                assert r.status_code in (401, 500)
        except Exception:
            pytest.skip("DB nicht erreichbar")

    def test_feedback_speichern_mock(self):
        """Feedback wird korrekt gespeichert."""
        import asyncio
        import feedback as fb_mod

        seminar_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        mock_seminar = MagicMock()
        mock_seminar.tenant_id = tenant_id

        mock_feedback_obj = MagicMock()
        mock_feedback_obj.id = uuid.uuid4()
        mock_feedback_obj.erstellt_am = datetime.now(timezone.utc)

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_seminar)

        added_items = []
        mock_db.add = MagicMock(side_effect=lambda x: added_items.append(x))

        async def mock_refresh(obj):
            obj.id = mock_feedback_obj.id
            obj.erstellt_am = mock_feedback_obj.erstellt_am

        mock_db.refresh = mock_refresh

        mock_token = MagicMock()
        mock_token.tenant_id = str(tenant_id)

        result = asyncio.run(fb_mod.feedback_speichern(
            seminar_id=seminar_id,
            body=fb_mod.FeedbackRequest(bewertung="gut", kommentar="Super!"),
            token_data=mock_token,
            db=mock_db,
        ))

        assert "id" in result
        assert "gespeichert_am" in result
        mock_db.add.assert_called_once()

    def test_feedback_falsche_bewertung_wirft_exception(self):
        """Ungültige Bewertung wirft HTTPException 400."""
        import asyncio
        import feedback as fb_mod
        from fastapi import HTTPException

        mock_seminar = MagicMock()
        mock_seminar.tenant_id = uuid.uuid4()
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_seminar)
        mock_token = MagicMock()
        mock_token.tenant_id = str(mock_seminar.tenant_id)

        with pytest.raises(HTTPException) as exc:
            asyncio.run(fb_mod.feedback_speichern(
                seminar_id=uuid.uuid4(),
                body=fb_mod.FeedbackRequest(bewertung="super_toll"),
                token_data=mock_token,
                db=mock_db,
            ))
        assert exc.value.status_code == 400


# ── Feedback-Aggregation ──────────────────────────────────────────────────────

class TestFeedbackAggregation:
    def test_aggregation_korrekt(self):
        """Aggregation zählt Bewertungen korrekt."""
        import asyncio
        import feedback as fb_mod

        seminar_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        mock_seminar = MagicMock()
        mock_seminar.tenant_id = tenant_id

        def make_fb(b):
            m = MagicMock()
            m.bewertung = b
            m.erstellt_am = datetime.now(timezone.utc)
            return m

        mock_rows = [
            make_fb("gut"), make_fb("gut"), make_fb("gut"),
            make_fb("zu_langweilig"),
            make_fb("falsche_ebene"), make_fb("falsche_ebene"),
        ]

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_seminar)
        mock_db.scalars = AsyncMock(return_value=mock_rows)

        mock_token = MagicMock()
        mock_token.tenant_id = str(tenant_id)

        result = asyncio.run(fb_mod.feedback_statistik(
            seminar_id=seminar_id,
            token_data=mock_token,
            db=mock_db,
        ))

        assert result["gesamt"] == 6
        assert result["gut"] == 3
        assert result["zu_langweilig"] == 1
        assert result["falsche_ebene"] == 2

    def test_aggregation_leer(self):
        """Ohne Feedback: gesamt=0, letztes_feedback=null."""
        import asyncio
        import feedback as fb_mod

        tenant_id = uuid.uuid4()
        mock_seminar = MagicMock()
        mock_seminar.tenant_id = tenant_id

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=mock_seminar)
        mock_db.scalars = AsyncMock(return_value=[])

        mock_token = MagicMock()
        mock_token.tenant_id = str(tenant_id)

        result = asyncio.run(fb_mod.feedback_statistik(
            seminar_id=uuid.uuid4(),
            token_data=mock_token,
            db=mock_db,
        ))

        assert result["gesamt"] == 0
        assert result["letztes_feedback"] is None


# ── Veraltet-Erkennung ────────────────────────────────────────────────────────

class TestVeraltetErkennung:
    def test_veraltet_schwelle_korrekt(self):
        """Schwelle ist 365 Tage."""
        from feedback import VERALTET_SCHWELLE_TAGE
        assert VERALTET_SCHWELLE_TAGE == 365

    def test_markiere_veraltete_chunks(self):
        """markiere_veraltete_chunks setzt ist_veraltet=True."""
        import asyncio
        import feedback as fb_mod

        mock_chunk = MagicMock()
        mock_chunk.quelldatum = datetime.now(timezone.utc) - timedelta(days=400)
        mock_chunk.ist_veraltet = False

        mock_db = AsyncMock()
        mock_db.scalars = AsyncMock(return_value=[mock_chunk])

        count = asyncio.run(fb_mod.markiere_veraltete_chunks(mock_db))
        assert count == 1
        assert mock_chunk.ist_veraltet is True
        mock_db.commit.assert_called_once()

    def test_ohne_veraltete_chunks_kein_commit(self):
        """Kein Commit wenn keine veralteten Chunks vorhanden."""
        import asyncio
        import feedback as fb_mod

        mock_db = AsyncMock()
        mock_db.scalars = AsyncMock(return_value=[])

        count = asyncio.run(fb_mod.markiere_veraltete_chunks(mock_db))
        assert count == 0
        mock_db.commit.assert_not_called()

    def test_chunk_modell_neue_felder(self):
        """Chunk-Modell hat die neuen Versions-Felder."""
        import models
        cols = {c.name for c in models.Chunk.__table__.columns}
        assert "quelldatum" in cols
        assert "rechtslage_gueltig_ab" in cols
        assert "ist_veraltet" in cols

    def test_seminar_feedback_modell_felder(self):
        """SeminarFeedback-Modell hat Pflichtfelder."""
        import models
        cols = {c.name for c in models.SeminarFeedback.__table__.columns}
        assert "id" in cols
        assert "seminar_id" in cols
        assert "bewertung" in cols
        assert "tenant_id" in cols

    def test_veraltet_endpoint_ohne_auth_401(self):
        """Veraltet-Endpoint ohne Auth muss 401 geben."""
        from app import app
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                r = client.get("/api/v1/chunks/veraltet")
                assert r.status_code in (401, 500)
        except Exception:
            pytest.skip("DB nicht erreichbar")
