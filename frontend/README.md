# ScriptNext

KI-gestütztes Seminar-Skript-Werkzeug für die BSt Next / HILO-Beratungsstellen. Aus vorhandenen Skript-PDFs (Fach- und Prozess-Themen) werden automatisch maßgeschneiderte Seminare generiert: Skript, Präsentation und Handout auf Basis der eingegebenen W-Fragen (Wann, Wo, Wer, Was, Wie lange).

## Repo-Struktur

```
ScriptNext/
├── backend/    ← FastAPI + PostgreSQL + pgvector (Sorty)
├── frontend/   ← Next.js 14 + TypeScript + Tailwind, BSt-Next-CI (Weby)
└── docs/       ← Konzept, Sprint-Status, Agents-Anforderungen (Docky)
```

## Docs

- [Konzept-Blatt](docs/ScriptNext-Konzept.html) — Ziel, Nutzer, Etappen E1–E6, Weichenstellungen, Rechtsquellen-DB, Team
- [Sprint 1 Status](docs/ScriptNext-Sprint1-Status.html) — Backend + Frontend live, API-Contract, Sprint-2-Backlog, Sicherheits-Hinweise
- [Agents-Anforderungen](docs/ScriptNext-Agents-Anforderungen.html) — Blueprints Backend + Frontend (ursprüngliche Version, Team-Namen dort noch Ragy/Formy, nach Realignment Sorty/Weby)

## Sprint-Stand (2026-09-27)

- **Sprint 1**: abgeschlossen — Backend + Frontend Sprint-1-Features live gewesen (Login, Upload, Themen-Übersicht mit CRUD + Merge). Preview auf Pandora aktuell offline (Plattform-Bug).
- **Sprint 2a** (Fundament + Härtung): abgeschlossen — pgvector aktiviert, CORS eingegrenzt, httpOnly-Cookie-Auth, Logout-Endpoint, Passwort-Ändern-Endpoint, 17/17 Backend-Tests grün, Frontend-Cookie-Umbau + Login-Flow-E2E grün.
- **Sprint 2b** (KI-Feature + Themen-Redaktion): Code komplett — Themen-Split-Endpoint, Seminar-Generierung mit W-Fragen und Zwei-Stufen-KI-Pipeline (Content + Didaktik), Word- und PPT-Export, Rechtsquellen-DB-Skeleton, Frontend mit Split-UI, W-Fragen-Formular, Vorschau-Screen, Download-Buttons, Feedback-Widget. Alle Tests grün.
- **Offen**: Live-Preview auf Pandora blockiert durch Plattform-Bug — Support-Ticket an EFINITI läuft.

## Team

- **catrin** — Product-Owner, Freigabe
- **Sorty** — Backend
- **Weby** — Frontend
- **Docky** — Koordination, Doku, CI-Templates
- **Irony** — Entscheider bei Uneinigkeit

## Kontakt

BSt Next GmbH i.G. · Reuschenberger Str. 11 · 41472 Neuss · info@bst-next.de
