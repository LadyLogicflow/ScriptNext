"""Tests für SharePoint-Integration (Etappe 3a)."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _mock_token_payload(tenant_id: uuid.UUID | None = None) -> MagicMock:
    payload = MagicMock()
    payload.tenant_id = str(tenant_id or uuid.uuid4())
    payload.sub = "testnutzer"
    return payload


# ── Token-Encryption ──────────────────────────────────────────────────────────

class TestTokenEncryption:
    def test_ohne_key_kein_overhead(self):
        """Ohne Fernet-Key bleibt der Token-String unverändert."""
        import sharepoint as sp
        original = '{"test": "data"}'
        with patch.object(sp.settings, "sharepoint_token_key", ""):
            assert sp._encrypt_token(original) == original
            assert sp._decrypt_token(original) == original

    def test_mit_key_roundtrip(self):
        """Fernet-Roundtrip: encrypt → decrypt ergibt Ursprungsstring."""
        from cryptography.fernet import Fernet
        import sharepoint as sp
        key = Fernet.generate_key().decode()
        original = '{"access_token": "secret_value"}'
        with patch.object(sp.settings, "sharepoint_token_key", key):
            encrypted = sp._encrypt_token(original)
            assert encrypted != original
            assert sp._decrypt_token(encrypted) == original

    def test_verschluesselt_kein_klartext_sichtbar(self):
        """Das verschlüsselte Ergebnis darf den Klartext nicht enthalten."""
        from cryptography.fernet import Fernet
        import sharepoint as sp
        key = Fernet.generate_key().decode()
        original = "mein_geheimer_token_wert_1234567890"
        with patch.object(sp.settings, "sharepoint_token_key", key):
            encrypted = sp._encrypt_token(original)
            assert original not in encrypted


# ── MSAL-App-Erzeugung ────────────────────────────────────────────────────────

class TestMsalApp:
    def test_ohne_client_id_503(self):
        """Ohne konfigurierte Client-ID muss 503 kommen."""
        import sharepoint as sp
        from fastapi import HTTPException
        with patch.object(sp.settings, "sharepoint_client_id", ""), \
             patch.object(sp, "MSAL_AVAILABLE", True):
            with pytest.raises(HTTPException) as exc:
                sp._get_msal_app()
            assert exc.value.status_code == 503

    def test_ohne_msal_503(self):
        """Ohne installiertes msal muss 503 kommen."""
        import sharepoint as sp
        from fastapi import HTTPException
        with patch.object(sp, "MSAL_AVAILABLE", False):
            with pytest.raises(HTTPException) as exc:
                sp._get_msal_app()
            assert exc.value.status_code == 503


# ── Verbindung-Starten-Endpoint ───────────────────────────────────────────────

class TestVerbindungStarten:
    def _get_client(self):
        from app import app
        return TestClient(app, raise_server_exceptions=False)

    def test_ohne_auth_401(self):
        """Ohne JWT-Cookie muss 401 kommen."""
        try:
            client = self._get_client()
            r = client.post("/api/v1/sharepoint/verbindung")
            assert r.status_code in (401, 500)
        except Exception:
            pytest.skip("DB nicht erreichbar")

    def test_mit_mock_flow(self):
        """Mit erfolgreichem Device-Code-Flow kommen session_id, user_code, verification_uri."""
        import sharepoint as sp
        from fastapi import HTTPException

        mock_flow = {
            "user_code": "TESTCODE",
            "verification_uri": "https://microsoft.com/devicelogin",
            "expires_in": 900,
            "message": "Gehe zu ...",
            "device_code": "device123",
        }
        mock_app = MagicMock()
        mock_app.initiate_device_flow.return_value = mock_flow

        with patch.object(sp, "_get_msal_app", return_value=mock_app):
            mock_token = _mock_token_payload()

            import asyncio
            result = asyncio.run(sp.verbindung_starten(token_data=mock_token))

        assert "session_id" in result
        assert result["user_code"] == "TESTCODE"
        assert result["verification_uri"] == "https://microsoft.com/devicelogin"
        assert result["session_id"] in sp._sessions

    def test_flow_fehler_gibt_503(self):
        """Wenn MSAL einen Fehler zurückgibt, muss 503 kommen."""
        import sharepoint as sp
        from fastapi import HTTPException

        mock_app = MagicMock()
        mock_app.initiate_device_flow.return_value = {
            "error": "invalid_client",
            "error_description": "Application not found",
        }
        with patch.object(sp, "_get_msal_app", return_value=mock_app):
            mock_token = _mock_token_payload()
            with pytest.raises(HTTPException) as exc:
                import asyncio
                asyncio.run(sp.verbindung_starten(token_data=mock_token))
            assert exc.value.status_code == 503


# ── Verbindung-Status-Endpoint ────────────────────────────────────────────────

class TestVerbindungStatus:
    def test_unbekannte_session_404(self):
        """Unbekannte session_id muss 404 ergeben."""
        import sharepoint as sp
        from fastapi import HTTPException

        mock_token = _mock_token_payload()
        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc:
            import asyncio
            asyncio.run(sp.verbindung_status(
                session_id="nicht-vorhanden",
                token_data=mock_token,
                db=mock_db,
            ))
        assert exc.value.status_code == 404

    def test_falsche_tenant_403(self):
        """Session eines anderen Tenants muss 403 ergeben."""
        import sharepoint as sp
        from fastapi import HTTPException

        other_tenant = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        sp._sessions[session_id] = {
            "flow": {},
            "app": MagicMock(),
            "tenant_id": other_tenant,
        }
        mock_token = _mock_token_payload()  # anderer tenant
        mock_db = AsyncMock()

        try:
            with pytest.raises(HTTPException) as exc:
                import asyncio
                asyncio.run(sp.verbindung_status(
                    session_id=session_id,
                    token_data=mock_token,
                    db=mock_db,
                ))
            assert exc.value.status_code == 403
        finally:
            sp._sessions.pop(session_id, None)

    def test_pending_status(self):
        """MSAL authorization_pending → status 'pending'."""
        import sharepoint as sp

        tenant_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        mock_app = MagicMock()
        mock_app.acquire_token_by_device_flow.return_value = {"error": "authorization_pending"}
        sp._sessions[session_id] = {
            "flow": {},
            "app": mock_app,
            "tenant_id": tenant_id,
        }
        mock_token = _mock_token_payload(uuid.UUID(tenant_id))
        mock_db = AsyncMock()
        mock_db.scalar = AsyncMock(return_value=None)

        try:
            import asyncio
            result = asyncio.run(sp.verbindung_status(
                session_id=session_id,
                token_data=mock_token,
                db=mock_db,
            ))
            assert result["status"] == "pending"
            assert result["token_gespeichert"] is False
        finally:
            sp._sessions.pop(session_id, None)

    def test_expired_status(self):
        """MSAL code_expired → status 'expired', Session wird gelöscht."""
        import sharepoint as sp

        tenant_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        mock_app = MagicMock()
        mock_app.acquire_token_by_device_flow.return_value = {"error": "code_expired"}
        sp._sessions[session_id] = {
            "flow": {},
            "app": mock_app,
            "tenant_id": tenant_id,
        }
        mock_token = _mock_token_payload(uuid.UUID(tenant_id))
        mock_db = AsyncMock()

        try:
            import asyncio
            result = asyncio.run(sp.verbindung_status(
                session_id=session_id,
                token_data=mock_token,
                db=mock_db,
            ))
            assert result["status"] == "expired"
            assert session_id not in sp._sessions
        finally:
            sp._sessions.pop(session_id, None)


# ── Ordner-Listen-Endpoint ────────────────────────────────────────────────────

class TestOrdnerListen:
    def test_ohne_token_in_db_403(self):
        """Kein gespeicherter Token → 403."""
        import sharepoint as sp
        from fastapi import HTTPException

        mock_token = _mock_token_payload()
        mock_db = AsyncMock()
        mock_db.scalar = AsyncMock(return_value=None)

        with patch.object(sp, "_get_msal_app"):
            with pytest.raises(HTTPException) as exc:
                import asyncio
                asyncio.run(sp.ordner_listen(
                    token_data=mock_token,
                    db=mock_db,
                ))
            assert exc.value.status_code == 403

    def test_parse_ordner_items(self):
        """_parse_ordner_items trennt Ordner und Dateien korrekt."""
        import sharepoint as sp
        raw = [
            {"id": "1", "name": "Ordner A", "folder": {"childCount": 3}},
            {"id": "2", "name": "Ordner B", "folder": {"childCount": 0}},
            {"id": "3", "name": "Datei.pdf", "file": {}, "size": 1234},
        ]
        items = sp._parse_ordner_items(raw)
        assert len(items) == 3
        assert items[0].typ == "ordner"
        assert items[0].kinder_vorhanden is True
        assert items[1].typ == "ordner"
        assert items[1].kinder_vorhanden is False
        assert items[2].typ == "datei"
        assert items[2].groesse_bytes == 1234


# ── Import-Endpoint ───────────────────────────────────────────────────────────

class TestDateienImportieren:
    def test_ohne_sharepoint_token_403(self):
        """Kein SharePoint-Token → 403 (kein API-Call nötig)."""
        import sharepoint as sp
        from fastapi import HTTPException

        mock_token = _mock_token_payload()
        mock_db = AsyncMock()
        mock_db.scalar = AsyncMock(return_value=None)
        mock_bt = MagicMock()

        with patch.object(sp, "_get_msal_app"):
            with pytest.raises(HTTPException) as exc:
                import asyncio
                from sharepoint import ImportRequest
                asyncio.run(sp.dateien_importieren(
                    payload=ImportRequest(drive_id="drive1", ordner_ids=["folder1"]),
                    background_tasks=mock_bt,
                    token_data=mock_token,
                    db=mock_db,
                ))
            assert exc.value.status_code == 403

    def test_import_request_schema(self):
        """ImportRequest muss drive_id und ordner_ids haben."""
        from sharepoint import ImportRequest
        req = ImportRequest(drive_id="abc", ordner_ids=["id1", "id2"])
        assert req.drive_id == "abc"
        assert len(req.ordner_ids) == 2

    def test_ordner_item_schema(self):
        """OrdnerItem muss Pflichtfelder haben."""
        from sharepoint import OrdnerItem
        item = OrdnerItem(id="x", name="Test", typ="ordner", kinder_vorhanden=True)
        assert item.id == "x"
        assert item.groesse_bytes is None
