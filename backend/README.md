# ScriptNext Backend

KI-gestützte Skript-Analyse. Python 3.12 + FastAPI + PostgreSQL + pgvector.

## Stack

- **FastAPI** — REST API
- **PostgreSQL + pgvector** — Datenspeicherung + Vektor-Suche
- **pdfplumber** — PDF-Text-Extraktion (OCR-Fallback: pytesseract)
- **OpenAI** — Embeddings (optional; ohne API-Key wird Embedding-Schritt übersprungen)
- **JWT** — Mandantenfähige Authentifizierung (Scope `scriptnext`)

## Schnellstart (Docker)

```bash
# .env anlegen
cp .env.example .env
# Admin-Passwort-Hash generieren:
python3 -c "from passlib.context import CryptContext; print(CryptContext(['bcrypt']).hash('dein-passwort'))"
# In .env eintragen: SCRIPTNEXT_ADMIN_PASSWORT_HASH=<hash>

docker-compose up --build
```

API läuft dann auf http://localhost:8000  
Swagger UI: http://localhost:8000/docs

## Lokale Entwicklung

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# PostgreSQL lokal nötig (oder nur docker-compose für DB starten)
docker-compose up db -d
uvicorn app:app --reload
```

## Tests

```bash
pytest test_app.py -v
```

## Endpunkte (Sprint 1)

| Methode | Pfad | Beschreibung |
|---------|------|-------------|
| POST | /api/v1/auth/login | Login, JWT holen |
| POST | /api/v1/upload | PDF hochladen (async) |
| GET | /api/v1/dokumente/{id} | Upload-Status pollen |
| GET | /api/v1/themen | Alle Themen des Tenants |
| PATCH | /api/v1/themen/{id} | Thema umbenennen |
| DELETE | /api/v1/themen/{id} | Thema löschen |
| POST | /api/v1/themen/merge | Themen zusammenführen |

## Mandantenfähigkeit

Jeder Nutzer gehört zu einem Tenant. Das JWT enthält `tenant_id` — alle Datenbankabfragen filtern automatisch auf diesen Tenant. Ein Nutzer kann niemals Daten eines anderen Tenants sehen oder ändern.

## ⚠️ DEV-ONLY Hinweise

- `SCRIPTNEXT_JWT_SECRET` **muss** vor Prod-Deploy auf einen starken zufälligen Wert gesetzt werden
- `SCRIPTNEXT_ADMIN_PASSWORT_HASH` ist ein Dev-Passwort — vor Prod ersetzen
- `CORS allow_origins=["*"]` muss vor Prod auf die tatsächliche Frontend-Domain eingeschränkt werden
- `localStorage` für Token-Speicherung im Frontend (MVP) — vor Prod auf httpOnly-Cookie umstellen
