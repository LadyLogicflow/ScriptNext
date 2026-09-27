"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

type DeviceCodeResponse = {
  session_id: string;
  device_code: string;
  user_code: string;
  verification_uri: string;
  expires_in: number;
  message: string;
};

type StatusResponse = {
  status: "pending" | "authorized" | "expired";
  token_gespeichert: boolean;
};

type OrdnerItem = {
  id: string;
  name: string;
  typ: "site" | "drive" | "folder" | "file";
  kinder_vorhanden: boolean;
  kinder?: OrdnerItem[];
};

type ImportResponse = {
  job_id: string;
  importiert: number;
  uebersprungen: number;
  fehler: string[];
};

export default function SharePointPage() {
  const router = useRouter();
  const [schritt, setSchritt] = useState<"init" | "auth" | "ordner" | "import">("init");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [deviceCode, setDeviceCode] = useState<DeviceCodeResponse | null>(null);
  const [status, setStatus] = useState<"pending" | "authorized" | "expired">("pending");
  const [laedt, setLaedt] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);

  // Ordner-Picker State
  const [sites, setSites] = useState<OrdnerItem[]>([]);
  const [selectedDriveId, setSelectedDriveId] = useState<string | null>(null);
  const [ordnerBaum, setOrdnerBaum] = useState<OrdnerItem[]>([]);
  const [selectedOrdnerIds, setSelectedOrdnerIds] = useState<Set<string>>(new Set());

  // Import State
  const [importResult, setImportResult] = useState<ImportResponse | null>(null);

  // Device-Code-Flow starten
  async function starteAuth() {
    setLaedt(true);
    setFehler(null);

    try {
      const res = await fetch(`${API_BASE}/api/v1/sharepoint/verbindung`, {
        method: "POST",
        credentials: "include",
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Verbindung fehlgeschlagen" }));
        throw new Error(data.detail ?? "Verbindung fehlgeschlagen");
      }

      const data: DeviceCodeResponse = await res.json();
      setDeviceCode(data);
      setSessionId(data.session_id);
      setSchritt("auth");
      setLaedt(false);

      // Status-Polling starten
      startePolling(data.session_id);
    } catch (err) {
      setFehler(err instanceof Error ? err.message : "Unbekannter Fehler");
      setLaedt(false);
    }
  }

  // Status-Polling (alle 5s)
  function startePolling(sid: string) {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/v1/sharepoint/verbindung/status?session_id=${sid}`, {
          credentials: "include",
        });

        if (!res.ok) {
          clearInterval(interval);
          setStatus("expired");
          return;
        }

        const data: StatusResponse = await res.json();
        setStatus(data.status);

        if (data.status === "authorized") {
          clearInterval(interval);
          // Sites laden
          await ladeSites();
          setSchritt("ordner");
        } else if (data.status === "expired") {
          clearInterval(interval);
        }
      } catch (err) {
        clearInterval(interval);
        setStatus("expired");
      }
    }, 5000); // 5s Polling

    // Cleanup bei Component-Unmount
    return () => clearInterval(interval);
  }

  // Sites laden
  async function ladeSites() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/sharepoint/ordner`, {
        credentials: "include",
      });

      if (!res.ok) {
        throw new Error("Sites konnten nicht geladen werden");
      }

      const data = await res.json();
      setSites(data.items || []);
    } catch (err) {
      setFehler(err instanceof Error ? err.message : "Sites konnten nicht geladen werden");
    }
  }

  // Ordner laden (nach Drive-Auswahl)
  async function ladeOrdner(driveId: string, parentId?: string) {
    setLaedt(true);
    try {
      const params = new URLSearchParams({ drive_id: driveId });
      if (parentId) params.append("parent_id", parentId);

      const res = await fetch(`${API_BASE}/api/v1/sharepoint/ordner?${params}`, {
        credentials: "include",
      });

      if (!res.ok) {
        throw new Error("Ordner konnten nicht geladen werden");
      }

      const data = await res.json();
      setOrdnerBaum(data.items || []);
      setLaedt(false);
    } catch (err) {
      setFehler(err instanceof Error ? err.message : "Ordner konnten nicht geladen werden");
      setLaedt(false);
    }
  }

  // Ordner-Selection Toggle
  function toggleOrdner(ordnerId: string) {
    const newSet = new Set(selectedOrdnerIds);
    if (newSet.has(ordnerId)) {
      newSet.delete(ordnerId);
    } else {
      newSet.add(ordnerId);
    }
    setSelectedOrdnerIds(newSet);
  }

  // Import starten
  async function starteImport() {
    if (!selectedDriveId || selectedOrdnerIds.size === 0) {
      setFehler("Bitte wählen Sie mindestens einen Ordner aus!");
      return;
    }

    setLaedt(true);
    setFehler(null);

    try {
      const res = await fetch(`${API_BASE}/api/v1/sharepoint/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          drive_id: selectedDriveId,
          ordner_ids: Array.from(selectedOrdnerIds),
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Import fehlgeschlagen" }));
        throw new Error(data.detail ?? "Import fehlgeschlagen");
      }

      const data: ImportResponse = await res.json();
      setImportResult(data);
      setSchritt("import");
      setLaedt(false);
    } catch (err) {
      setFehler(err instanceof Error ? err.message : "Import fehlgeschlagen");
      setLaedt(false);
    }
  }

  async function handleLogout() {
    try {
      await fetch(`${API_BASE}/api/v1/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } catch (err) {
      // Logout trotzdem durchführen
    }
    router.push("/");
  }

  return (
    <main className="min-h-screen bg-gradient-to-b from-white to-gray-50 p-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8 pt-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-navy rounded-xl">
              <svg className="w-8 h-8 text-lime" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" />
              </svg>
            </div>
            <div>
              <h1 className="text-2xl font-bold text-navy">ScriptNext</h1>
              <p className="text-gray-600 text-sm">SharePoint-Anbindung</p>
            </div>
          </div>
          <div className="flex gap-3">
            <Link
              href="/upload"
              className="px-4 py-2 text-navy hover:bg-gray-100 rounded-lg transition font-medium"
            >
              Zurück
            </Link>
            <button
              onClick={handleLogout}
              className="px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition font-medium"
            >
              Abmelden
            </button>
          </div>
        </div>

        {/* Content */}
        {schritt === "init" && (
          <div className="bg-white rounded-xl shadow-lg p-8">
            <h2 className="text-xl font-semibold text-navy mb-4">SharePoint verbinden</h2>
            <p className="text-gray-600 mb-6">
              Verbinden Sie Ihr SharePoint-Konto um Dokumente als Wissensquellen zu importieren.
            </p>
            {fehler && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
                <p className="text-red-600">{fehler}</p>
              </div>
            )}
            <button
              onClick={starteAuth}
              disabled={laedt}
              className="px-6 py-3 bg-navy text-white rounded-lg font-semibold hover:bg-navy-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {laedt ? "Startet..." : "SharePoint verbinden"}
            </button>
          </div>
        )}

        {schritt === "auth" && deviceCode && (
          <div className="bg-white rounded-xl shadow-lg p-8">
            <h2 className="text-xl font-semibold text-navy mb-4">Authentifizierung</h2>

            {status === "pending" && (
              <>
                <p className="text-gray-600 mb-6">
                  Öffnen Sie die folgende URL in einem neuen Tab und geben Sie den Code ein:
                </p>

                {/* Verification URL */}
                <div className="bg-gray-50 rounded-lg p-4 mb-4">
                  <p className="text-sm text-gray-600 mb-2">URL:</p>
                  <a
                    href={deviceCode.verification_uri}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-lime font-medium hover:underline"
                  >
                    {deviceCode.verification_uri}
                  </a>
                </div>

                {/* User Code */}
                <div className="bg-navy rounded-lg p-6 mb-6 text-center">
                  <p className="text-lime text-sm mb-2">Ihr Code:</p>
                  <p className="text-white text-4xl font-bold tracking-wider">
                    {deviceCode.user_code}
                  </p>
                </div>

                {/* Open Button */}
                <a
                  href={deviceCode.verification_uri}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block px-6 py-3 bg-lime text-navy rounded-lg font-semibold hover:bg-lime-600 transition mb-6"
                >
                  In neuem Tab öffnen
                </a>

                {/* Polling Spinner */}
                <div className="flex items-center gap-3 text-gray-600">
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-navy"></div>
                  <p>Warte auf Authentifizierung...</p>
                </div>
              </>
            )}

            {status === "expired" && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <p className="text-red-600 mb-4">Der Code ist abgelaufen. Bitte starten Sie den Vorgang erneut.</p>
                <button
                  onClick={() => { setSchritt("init"); setDeviceCode(null); setStatus("pending"); }}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition"
                >
                  Neu starten
                </button>
              </div>
            )}
          </div>
        )}

        {schritt === "ordner" && (
          <div className="bg-white rounded-xl shadow-lg p-8">
            <h2 className="text-xl font-semibold text-navy mb-4">📁 Ordner auswählen</h2>

            {fehler && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
                <p className="text-red-600">{fehler}</p>
              </div>
            )}

            {/* Sites/Drives Auswahl */}
            <div className="mb-6">
              <h3 className="text-lg font-semibold text-navy mb-3">SharePoint-Sites:</h3>
              {sites.length === 0 && <p className="text-gray-500">Lädt...</p>}
              <div className="space-y-2">
                {sites.map((site) => (
                  <div key={site.id} className="border border-gray-200 rounded-lg p-4">
                    <button
                      onClick={() => {
                        setSelectedDriveId(site.id);
                        ladeOrdner(site.id);
                      }}
                      className={`text-left w-full font-medium ${
                        selectedDriveId === site.id ? "text-lime" : "text-navy hover:text-lime"
                      }`}
                    >
                      {site.name}
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Ordner-Baum */}
            {selectedDriveId && ordnerBaum.length > 0 && (
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-navy mb-3">Ordner:</h3>
                <div className="space-y-2">
                  {ordnerBaum.map((ordner) => (
                    <div key={ordner.id} className="border border-gray-200 rounded-lg p-4">
                      <label className="flex items-center gap-3 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={selectedOrdnerIds.has(ordner.id)}
                          onChange={() => toggleOrdner(ordner.id)}
                          className="w-5 h-5 text-lime border-gray-300 rounded focus:ring-lime"
                        />
                        <span className="text-navy font-medium">{ordner.name}</span>
                        {ordner.typ === "file" && (
                          <span className="text-xs text-gray-500 ml-auto">PDF</span>
                        )}
                      </label>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Import Button */}
            {selectedOrdnerIds.size > 0 && (
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setSelectedOrdnerIds(new Set())}
                  className="px-6 py-3 text-navy hover:bg-gray-100 rounded-lg transition font-semibold"
                >
                  Auswahl zurücksetzen
                </button>
                <button
                  onClick={starteImport}
                  disabled={laedt}
                  className="px-6 py-3 bg-navy text-white rounded-lg font-semibold hover:bg-navy-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {laedt ? "Importiere..." : `${selectedOrdnerIds.size} Ordner importieren`}
                </button>
              </div>
            )}
          </div>
        )}

        {schritt === "import" && importResult && (
          <div className="bg-white rounded-xl shadow-lg p-8">
            <h2 className="text-xl font-semibold text-navy mb-4">✅ Import abgeschlossen!</h2>

            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="bg-lime bg-opacity-10 rounded-lg p-4">
                <p className="text-sm text-gray-600 mb-1">Importiert:</p>
                <p className="text-3xl font-bold text-lime">{importResult.importiert}</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-sm text-gray-600 mb-1">Übersprungen:</p>
                <p className="text-3xl font-bold text-gray-600">{importResult.uebersprungen}</p>
              </div>
            </div>

            {importResult.fehler.length > 0 && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
                <p className="font-semibold text-red-600 mb-2">Fehler:</p>
                <ul className="list-disc list-inside space-y-1">
                  {importResult.fehler.map((f, i) => (
                    <li key={i} className="text-sm text-red-600">{f}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex gap-3">
              <Link
                href="/upload"
                className="px-6 py-3 bg-navy text-white rounded-lg font-semibold hover:bg-navy-700 transition"
              >
                Zu den Themen
              </Link>
              <button
                onClick={() => {
                  setSchritt("ordner");
                  setSelectedOrdnerIds(new Set());
                  setImportResult(null);
                }}
                className="px-6 py-3 text-navy hover:bg-gray-100 rounded-lg transition font-semibold"
              >
                Weitere Ordner importieren
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
