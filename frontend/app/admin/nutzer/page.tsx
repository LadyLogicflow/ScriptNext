"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

type Rolle = "admin" | "editor" | "viewer";

type Nutzer = {
  id: number;
  email: string;
  rolle: Rolle;
  ist_aktiv: boolean;
  erstellt_am: string;
};

type NutzerListResponse = {
  nutzer: Nutzer[];
  total: number;
};

export default function AdminNutzerPage() {
  const router = useRouter();
  const [nutzer, setNutzer] = useState<Nutzer[]>([]);
  const [laedt, setLaedt] = useState(true);
  const [fehler, setFehler] = useState<string | null>(null);
  const [showAnlegenModal, setShowAnlegenModal] = useState(false);
  const [showLoeschenModal, setShowLoeschenModal] = useState(false);
  const [loeschenNutzer, setLoeschenNutzer] = useState<Nutzer | null>(null);

  // Anlegen-Modal State
  const [neueEmail, setNeueEmail] = useState("");
  const [neueRolle, setNeueRolle] = useState<Rolle>("editor");
  const [anlegenLaedt, setAnlegenLaedt] = useState(false);

  useEffect(() => {
    laden();
  }, []);

  async function laden() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/nutzer`, {
        credentials: "include",
      });

      if (res.status === 403) {
        // Keine Admin-Berechtigung
        setFehler("Keine Berechtigung - nur für Admins");
        setLaedt(false);
        return;
      }

      if (!res.ok) {
        setFehler("Nutzer konnten nicht geladen werden");
        setLaedt(false);
        return;
      }

      const data: NutzerListResponse = await res.json();
      setNutzer(data.nutzer ?? []);
      setLaedt(false);
    } catch (err) {
      setFehler("Verbindung fehlgeschlagen");
      setLaedt(false);
    }
  }

  async function anlegen() {
    if (!neueEmail.trim()) {
      alert("Bitte E-Mail eingeben");
      return;
    }

    setAnlegenLaedt(true);

    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/nutzer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          email: neueEmail,
          rolle: neueRolle,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Anlegen fehlgeschlagen" }));
        throw new Error(data.detail ?? "Anlegen fehlgeschlagen");
      }

      setShowAnlegenModal(false);
      setNeueEmail("");
      setNeueRolle("editor");
      setAnlegenLaedt(false);
      laden();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Fehler beim Anlegen");
      setAnlegenLaedt(false);
    }
  }

  async function rolleAendern(nutzerId: number, neueRolle: Rolle) {
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/nutzer/${nutzerId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ rolle: neueRolle }),
      });

      if (!res.ok) {
        alert("Rolle konnte nicht geändert werden");
        return;
      }

      laden();
    } catch (err) {
      alert("Verbindung fehlgeschlagen");
    }
  }

  async function loeschen() {
    if (!loeschenNutzer) return;

    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/nutzer/${loeschenNutzer.id}`, {
        method: "DELETE",
        credentials: "include",
      });

      if (!res.ok) {
        alert("Löschen fehlgeschlagen");
        return;
      }

      setShowLoeschenModal(false);
      setLoeschenNutzer(null);
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

  function getRolleLabel(rolle: Rolle): string {
    switch (rolle) {
      case "admin":
        return "👑 Admin";
      case "editor":
        return "✏️ Editor";
      case "viewer":
        return "👁️ Viewer";
      default:
        return rolle;
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
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
                />
              </svg>
            </div>
            <div>
              <h1 className="text-2xl font-bold text-navy">ScriptNext Admin</h1>
              <p className="text-gray-600 text-sm">Nutzer-Verwaltung</p>
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

        {/* Nutzer-Tabelle */}
        <div className="bg-white rounded-xl shadow-lg p-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-navy">Nutzer</h2>
            <button
              onClick={() => setShowAnlegenModal(true)}
              className="px-4 py-2 bg-lime text-navy rounded-lg hover:bg-lime-600 transition font-semibold"
            >
              + Nutzer anlegen
            </button>
          </div>

          {fehler && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm mb-6">
              {fehler}
            </div>
          )}

          {laedt ? (
            <p className="text-gray-500">Lädt...</p>
          ) : nutzer.length === 0 ? (
            <p className="text-gray-500">Keine Nutzer vorhanden.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-3 px-4 font-semibold text-navy">E-Mail</th>
                    <th className="text-left py-3 px-4 font-semibold text-navy">Rolle</th>
                    <th className="text-left py-3 px-4 font-semibold text-navy">Status</th>
                    <th className="text-left py-3 px-4 font-semibold text-navy">Erstellt am</th>
                    <th className="text-right py-3 px-4 font-semibold text-navy">Aktionen</th>
                  </tr>
                </thead>
                <tbody>
                  {nutzer.map((n) => (
                    <tr key={n.id} className="border-b border-gray-100 hover:bg-gray-50 transition">
                      <td className="py-3 px-4 text-gray-900">{n.email}</td>
                      <td className="py-3 px-4">
                        <select
                          value={n.rolle}
                          onChange={(e) => rolleAendern(n.id, e.target.value as Rolle)}
                          className="px-3 py-1 border border-gray-300 rounded-lg focus:ring-2 focus:ring-lime outline-none text-sm"
                        >
                          <option value="admin">👑 Admin</option>
                          <option value="editor">✏️ Editor</option>
                          <option value="viewer">👁️ Viewer</option>
                        </select>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`px-3 py-1 rounded-full text-xs font-semibold ${
                            n.ist_aktiv
                              ? "bg-green-100 text-green-800"
                              : "bg-gray-100 text-gray-600"
                          }`}
                        >
                          {n.ist_aktiv ? "✓ Aktiv" : "○ Inaktiv"}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-gray-600 text-sm">
                        {new Date(n.erstellt_am).toLocaleDateString("de-DE")}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => {
                            setLoeschenNutzer(n);
                            setShowLoeschenModal(true);
                          }}
                          className="px-3 py-1 bg-red-100 text-red-600 rounded-lg hover:bg-red-200 transition text-sm font-medium"
                        >
                          Löschen
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Anlegen-Modal */}
        {showAnlegenModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-xl shadow-2xl max-w-md w-full">
              <div className="border-b border-gray-200 p-6">
                <h2 className="text-2xl font-bold text-navy">Nutzer anlegen</h2>
              </div>

              <div className="p-6 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    E-Mail-Adresse
                  </label>
                  <input
                    type="email"
                    value={neueEmail}
                    onChange={(e) => setNeueEmail(e.target.value)}
                    placeholder="nutzer@example.com"
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-lime outline-none"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Rolle</label>
                  <select
                    value={neueRolle}
                    onChange={(e) => setNeueRolle(e.target.value as Rolle)}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-lime outline-none"
                  >
                    <option value="admin">👑 Admin</option>
                    <option value="editor">✏️ Editor</option>
                    <option value="viewer">👁️ Viewer</option>
                  </select>
                </div>

                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <p className="text-sm text-blue-900">
                    💡 Der Nutzer erhält nach dem Anlegen eine E-Mail mit einem Link zum Setzen
                    des Passworts.
                  </p>
                </div>

                <div className="flex gap-3 pt-4">
                  <button
                    onClick={anlegen}
                    disabled={anlegenLaedt}
                    className="flex-1 px-6 py-3 bg-navy text-white rounded-lg font-semibold hover:bg-navy-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {anlegenLaedt ? "Legt an..." : "Anlegen"}
                  </button>
                  <button
                    onClick={() => {
                      setShowAnlegenModal(false);
                      setNeueEmail("");
                      setNeueRolle("editor");
                    }}
                    disabled={anlegenLaedt}
                    className="px-6 py-3 text-gray-600 hover:bg-gray-100 rounded-lg transition font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Abbrechen
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Löschen-Bestätigungs-Modal */}
        {showLoeschenModal && loeschenNutzer && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-xl shadow-2xl max-w-md w-full">
              <div className="border-b border-gray-200 p-6">
                <h2 className="text-2xl font-bold text-red-600">Nutzer löschen?</h2>
              </div>

              <div className="p-6">
                <p className="text-gray-700 mb-4">
                  Möchten Sie den Nutzer <strong>{loeschenNutzer.email}</strong> wirklich löschen?
                </p>
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                  <p className="text-sm text-red-900">
                    ⚠️ Diese Aktion kann nicht rückgängig gemacht werden!
                  </p>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={loeschen}
                    className="flex-1 px-6 py-3 bg-red-600 text-white rounded-lg font-semibold hover:bg-red-700 transition"
                  >
                    Löschen
                  </button>
                  <button
                    onClick={() => {
                      setShowLoeschenModal(false);
                      setLoeschenNutzer(null);
                    }}
                    className="px-6 py-3 text-gray-600 hover:bg-gray-100 rounded-lg transition font-semibold"
                  >
                    Abbrechen
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
