"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

type Thema = {
  id: number;
  titel: string;
  beschreibung: string;
  erstellt_am: string;
};

export default function ThemenPage() {
  const router = useRouter();
  const [themen, setThemen] = useState<Thema[]>([]);
  const [laedt, setLaedt] = useState(true);
  const [fehler, setFehler] = useState<string | null>(null);
  const [bearbeitenId, setBearbeitenId] = useState<number | null>(null);
  const [bearbeitenTitel, setBearbeitenTitel] = useState("");
  const [bearbeitenBeschreibung, setBearbeitenBeschreibung] = useState("");
  const [mergeIds, setMergeIds] = useState<number[]>([]);

  useEffect(() => {
    // Cookie-basierte Auth - kein Check mehr nötig
    // Falls nicht eingeloggt, gibt Backend 401 zurück
    laden();
  }, []);

  async function laden() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/themen`, {
        credentials: "include",
      });

      if (!res.ok) {
        setFehler("Themen konnten nicht geladen werden");
        setLaedt(false);
        return;
      }

      const data = await res.json();
      setThemen(data.themen ?? []);
      setLaedt(false);
    } catch (err) {
      setFehler("Verbindung fehlgeschlagen");
      setLaedt(false);
    }
  }

  async function bearbeiten(id: number) {
    try {
      const res = await fetch(`${API_BASE}/api/v1/themen/${id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          titel: bearbeitenTitel,
          beschreibung: bearbeitenBeschreibung,
        }),
      });

      if (!res.ok) {
        alert("Bearbeiten fehlgeschlagen");
        return;
      }

      setBearbeitenId(null);
      laden();
    } catch (err) {
      alert("Verbindung fehlgeschlagen");
    }
  }

  async function loeschen(id: number) {
    if (!confirm("Thema wirklich löschen?")) return;

    try {
      const res = await fetch(`${API_BASE}/api/v1/themen/${id}`, {
        method: "DELETE",
        credentials: "include",
      });

      if (!res.ok) {
        alert("Löschen fehlgeschlagen");
        return;
      }

      laden();
    } catch (err) {
      alert("Verbindung fehlgeschlagen");
    }
  }

  async function zusammenfuehren() {
    if (mergeIds.length < 2) {
      alert("Bitte mindestens 2 Themen auswählen");
      return;
    }

    const neuerTitel = prompt("Titel für das zusammengeführte Thema:");
    if (!neuerTitel) return;

    try {
      const res = await fetch(`${API_BASE}/api/v1/themen/merge`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          thema_ids: mergeIds,
          neuer_titel: neuerTitel,
        }),
      });

      if (!res.ok) {
        alert("Zusammenführen fehlgeschlagen");
        return;
      }

      setMergeIds([]);
      laden();
    } catch (err) {
      alert("Verbindung fehlgeschlagen");
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

  function toggleMerge(id: number) {
    if (mergeIds.includes(id)) {
      setMergeIds(mergeIds.filter((x) => x !== id));
    } else {
      setMergeIds([...mergeIds, id]);
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-b from-white to-gray-50 p-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8 pt-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-navy rounded-xl">
              <svg className="w-8 h-8 text-lime" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
              </svg>
            </div>
            <div>
              <h1 className="text-2xl font-bold text-navy">ScriptNext</h1>
              <p className="text-gray-600 text-sm">Themen-Übersicht</p>
            </div>
          </div>
          <div className="flex gap-3">
            <Link
              href="/upload"
              className="px-4 py-2 bg-lime text-navy hover:bg-lime-600 rounded-lg transition font-semibold"
            >
              Neues Dokument
            </Link>
            <button
              onClick={handleLogout}
              className="px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition font-medium"
            >
              Abmelden
            </button>
          </div>
        </div>

        {/* Themen-Liste */}
        <div className="bg-white rounded-xl shadow-lg p-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-navy">Extrahierte Themen</h2>
            {mergeIds.length >= 2 && (
              <button
                onClick={zusammenfuehren}
                className="px-4 py-2 bg-navy text-white rounded-lg hover:bg-navy-700 transition font-semibold text-sm"
              >
                {mergeIds.length} Themen zusammenführen
              </button>
            )}
          </div>

          {fehler && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm mb-6">
              {fehler}
            </div>
          )}

          {laedt ? (
            <p className="text-gray-500">Lädt...</p>
          ) : themen.length === 0 ? (
            <p className="text-gray-500">Keine Themen vorhanden. Lade ein Dokument hoch!</p>
          ) : (
            <div className="space-y-4">
              {themen.map((thema) => (
                <div
                  key={thema.id}
                  className={`border rounded-lg p-4 transition ${
                    mergeIds.includes(thema.id)
                      ? "border-lime bg-lime-50"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  {bearbeitenId === thema.id ? (
                    <div className="space-y-3">
                      <input
                        type="text"
                        value={bearbeitenTitel}
                        onChange={(e) => setBearbeitenTitel(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-lime outline-none"
                        placeholder="Titel"
                      />
                      <textarea
                        value={bearbeitenBeschreibung}
                        onChange={(e) => setBearbeitenBeschreibung(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-lime outline-none"
                        rows={3}
                        placeholder="Beschreibung"
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={() => bearbeiten(thema.id)}
                          className="px-4 py-2 bg-navy text-white rounded-lg hover:bg-navy-700 transition text-sm font-semibold"
                        >
                          Speichern
                        </button>
                        <button
                          onClick={() => setBearbeitenId(null)}
                          className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition text-sm font-semibold"
                        >
                          Abbrechen
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <h3 className="text-lg font-semibold text-navy mb-1">{thema.titel}</h3>
                          <p className="text-gray-600 text-sm mb-2">{thema.beschreibung}</p>
                          <p className="text-gray-400 text-xs">
                            Erstellt am: {new Date(thema.erstellt_am).toLocaleString("de-DE")}
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => toggleMerge(thema.id)}
                            className={`px-3 py-1 rounded-lg text-sm font-medium transition ${
                              mergeIds.includes(thema.id)
                                ? "bg-lime text-navy"
                                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                            }`}
                          >
                            {mergeIds.includes(thema.id) ? "✓" : "Merge"}
                          </button>
                          <button
                            onClick={() => {
                              setBearbeitenId(thema.id);
                              setBearbeitenTitel(thema.titel);
                              setBearbeitenBeschreibung(thema.beschreibung);
                            }}
                            className="px-3 py-1 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200 transition text-sm font-medium"
                          >
                            Bearbeiten
                          </button>
                          <button
                            onClick={() => loeschen(thema.id)}
                            className="px-3 py-1 bg-red-100 text-red-600 rounded-lg hover:bg-red-200 transition text-sm font-medium"
                          >
                            Löschen
                          </button>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
