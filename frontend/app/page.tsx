"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export default function LoginPage() {
  const router = useRouter();
  const [benutzername, setBenutzername] = useState("");
  const [passwort, setPasswort] = useState("");
  const [fehler, setFehler] = useState<string | null>(null);
  const [laedt, setLaedt] = useState(false);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setFehler(null);
    setLaedt(true);

    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ benutzername, passwort }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Login fehlgeschlagen" }));
        setFehler(data.detail ?? "Login fehlgeschlagen");
        setLaedt(false);
        return;
      }

      // Cookie wird automatisch gesetzt - kein localStorage mehr!
      // Zur Upload-Seite weiterleiten
      router.push("/upload");
    } catch (err) {
      setFehler("Verbindung fehlgeschlagen. Bitte später erneut versuchen.");
      setLaedt(false);
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-b from-white to-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo/Header */}
        <div className="text-center mb-8">
          <div className="inline-block p-6 bg-navy rounded-2xl mb-4 shadow-lg">
            <svg className="w-12 h-12 text-lime" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-navy mb-2">ScriptNext</h1>
          <p className="text-gray-600">Dokumenten-Ingest und Themen-Extraktion</p>
        </div>

        {/* Login-Formular */}
        <form onSubmit={handleLogin} className="bg-white rounded-xl shadow-lg p-8 space-y-6">
          <h2 className="text-xl font-semibold text-navy">Anmelden</h2>

          {fehler && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
              {fehler}
            </div>
          )}

          <div>
            <label htmlFor="benutzername" className="block text-sm font-medium text-gray-700 mb-2">
              Benutzername
            </label>
            <input
              id="benutzername"
              type="text"
              required
              value={benutzername}
              onChange={(e) => setBenutzername(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-lime focus:border-transparent outline-none transition"
              placeholder="admin"
            />
          </div>

          <div>
            <label htmlFor="passwort" className="block text-sm font-medium text-gray-700 mb-2">
              Passwort
            </label>
            <input
              id="passwort"
              type="password"
              required
              value={passwort}
              onChange={(e) => setPasswort(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-lime focus:border-transparent outline-none transition"
            />
          </div>

          <button
            type="submit"
            disabled={laedt}
            className="w-full bg-navy text-white py-3 px-6 rounded-lg font-semibold hover:bg-navy-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {laedt ? "Wird angemeldet..." : "Anmelden"}
          </button>
        </form>

        {/* Footer */}
        <div className="mt-6 text-center text-sm text-gray-500">
          <p>Sprint 1 MVP - BSt Next GmbH</p>
        </div>
      </div>
    </main>
  );
}
