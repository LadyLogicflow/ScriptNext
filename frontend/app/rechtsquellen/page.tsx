"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

type RechtsquelleTyp = "gesetz" | "urteil" | "schreiben" | "alle";

type Rechtsquelle = {
  id: string;
  typ: "gesetz" | "urteil" | "schreiben";
  titel: string;
  paragraph?: string;
  gesetz?: string;
  aktenzeichen?: string;
  datum: string;
  kurztext: string;
  quelle_url: string;
  volltext?: string;
};

type ListResponse = {
  items: Rechtsquelle[];
  total: number;
};

export default function RechtsquellenPage() {
  const router = useRouter();
  const [filter, setFilter] = useState<RechtsquelleTyp>("alle");
  const [suchbegriff, setSuchbegriff] = useState("");
  const [debouncedSuche, setDebouncedSuche] = useState("");
  const [rechtsquellen, setRechtsquellen] = useState<Rechtsquelle[]>([]);
  const [total, setTotal] = useState(0);
  const [laedt, setLaedt] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const [selectedQuelle, setSelectedQuelle] = useState<Rechtsquelle | null>(null);
  const [showModal, setShowModal] = useState(false);

  // Debounce Suche (500ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSuche(suchbegriff);
    }, 500);

    return () => clearTimeout(timer);
  }, [suchbegriff]);

  // Rechtsquellen laden (bei Filter- oder Suche-Änderung)
  useEffect(() => {
    ladeRechtsquellen();
  }, [filter, debouncedSuche]);

  async function ladeRechtsquellen() {
    setLaedt(true);
    setFehler(null);

    try {
      const params = new URLSearchParams();
      if (filter !== "alle") params.append("typ", filter);
      if (debouncedSuche) params.append("q", debouncedSuche);
      params.append("limit", "50");
      params.append("offset", "0");

      const res = await fetch(`${API_BASE}/api/v1/rechtsquellen?${params}`, {
        credentials: "include",
      });

      if (!res.ok) {
        throw new Error("Rechtsquellen konnten nicht geladen werden");
      }

      const data: ListResponse = await res.json();
      setRechtsquellen(data.items || []);
      setTotal(data.total || 0);
      setLaedt(false);
    } catch (err) {
      setFehler(err instanceof Error ? err.message : "Fehler beim Laden");
      setLaedt(false);
    }
  }

  async function ladeDetail(id: string) {
    try {
      const res = await fetch(`${API_BASE}/api/v1/rechtsquellen/${id}`, {
        credentials: "include",
      });

      if (!res.ok) {
        throw new Error("Detail konnte nicht geladen werden");
      }

      const data: Rechtsquelle = await res.json();
      setSelectedQuelle(data);
      setShowModal(true);
    } catch (err) {
      setFehler(err instanceof Error ? err.message : "Detail-Fehler");
    }
  }

  function closeModal() {
    setShowModal(false);
    setSelectedQuelle(null);
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

  function formatDatum(datum: string): string {
    try {
      const d = new Date(datum);
      return d.toLocaleDateString("de-DE");
    } catch {
      return datum;
    }
  }

  function getTypLabel(typ: string): string {
    switch (typ) {
      case "gesetz": return "📜 Gesetz";
      case "urteil": return "⚖️ Urteil";
      case "schreiben": return "📝 BMF-Schreiben";
      default: return typ;
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-b from-white to-gray-50 p-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8 pt-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-navy rounded-xl">
              <svg className="w-8 h-8 text-lime" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>
            <div>
              <h1 className="text-2xl font-bold text-navy">ScriptNext</h1>
              <p className="text-gray-600 text-sm">Rechtsquellen-Übersicht</p>
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

        {/* Filter & Suche */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          {/* Filter-Buttons */}
          <div className="flex gap-3 mb-4 flex-wrap">
            {(["alle", "gesetz", "urteil", "schreiben"] as RechtsquelleTyp[]).map((typ) => (
              <button
                key={typ}
                onClick={() => setFilter(typ)}
                className={`px-4 py-2 rounded-lg font-medium transition ${
                  filter === typ
                    ? "bg-navy text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                {typ === "alle" && "Alle"}
                {typ === "gesetz" && "📜 Gesetze"}
                {typ === "urteil" && "⚖️ Urteile"}
                {typ === "schreiben" && "📝 BMF-Schreiben"}
              </button>
            ))}
          </div>

          {/* Suchfeld */}
          <div className="relative">
            <input
              type="text"
              value={suchbegriff}
              onChange={(e) => setSuchbegriff(e.target.value)}
              placeholder="Volltext-Suche (z.B. Aktenzeichen, Paragraph, Titel)..."
              className="w-full px-4 py-3 pr-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-lime outline-none"
            />
            <svg
              className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>

          {/* Ergebnis-Zähler */}
          <p className="text-sm text-gray-600 mt-3">
            {total} Rechtsquelle{total !== 1 ? "n" : ""} gefunden
          </p>
        </div>

        {/* Fehler */}
        {fehler && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-red-600">{fehler}</p>
          </div>
        )}

        {/* Ergebnis-Liste */}
        {laedt ? (
          <div className="bg-white rounded-xl shadow-lg p-8 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-navy mx-auto"></div>
            <p className="text-gray-600 mt-4">Lädt...</p>
          </div>
        ) : rechtsquellen.length === 0 ? (
          <div className="bg-white rounded-xl shadow-lg p-8 text-center">
            <p className="text-gray-500">Keine Rechtsquellen gefunden.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {rechtsquellen.map((quelle) => (
              <div
                key={quelle.id}
                className="bg-white rounded-xl shadow-lg p-6 hover:shadow-xl transition cursor-pointer"
                onClick={() => ladeDetail(quelle.id)}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">{getTypLabel(quelle.typ).split(" ")[0]}</span>
                    <div>
                      <h3 className="text-lg font-semibold text-navy">{quelle.titel}</h3>
                      {(quelle.paragraph || quelle.aktenzeichen) && (
                        <p className="text-sm text-gray-600">
                          {quelle.paragraph && `${quelle.gesetz} ${quelle.paragraph}`}
                          {quelle.aktenzeichen && `Az: ${quelle.aktenzeichen}`}
                        </p>
                      )}
                    </div>
                  </div>
                  <span className="text-sm text-gray-500">{formatDatum(quelle.datum)}</span>
                </div>
                <p className="text-gray-700 text-sm line-clamp-2">{quelle.kurztext}</p>
                <div className="mt-3 flex items-center gap-2 text-sm">
                  <span className="px-3 py-1 bg-lime bg-opacity-20 text-navy rounded-full font-medium">
                    {getTypLabel(quelle.typ)}
                  </span>
                  {quelle.quelle_url && (
                    <a
                      href={quelle.quelle_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="text-lime hover:underline"
                    >
                      Original-Quelle →
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Detail-Modal */}
        {showModal && selectedQuelle && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
              {/* Modal Header */}
              <div className="sticky top-0 bg-white border-b border-gray-200 p-6">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                      <span className="text-3xl">{getTypLabel(selectedQuelle.typ).split(" ")[0]}</span>
                      <h2 className="text-2xl font-bold text-navy">{selectedQuelle.titel}</h2>
                    </div>
                    {(selectedQuelle.paragraph || selectedQuelle.aktenzeichen) && (
                      <p className="text-gray-600">
                        {selectedQuelle.paragraph && `${selectedQuelle.gesetz} ${selectedQuelle.paragraph}`}
                        {selectedQuelle.aktenzeichen && `Az: ${selectedQuelle.aktenzeichen}`}
                      </p>
                    )}
                    <p className="text-sm text-gray-500 mt-1">{formatDatum(selectedQuelle.datum)}</p>
                  </div>
                  <button
                    onClick={closeModal}
                    className="p-2 hover:bg-gray-100 rounded-lg transition"
                  >
                    <svg className="w-6 h-6 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>

              {/* Modal Body */}
              <div className="p-6">
                <div className="mb-6">
                  <h3 className="text-lg font-semibold text-navy mb-3">Kurztext:</h3>
                  <p className="text-gray-700">{selectedQuelle.kurztext}</p>
                </div>

                {selectedQuelle.volltext && (
                  <div className="mb-6">
                    <h3 className="text-lg font-semibold text-navy mb-3">Volltext:</h3>
                    <div className="bg-gray-50 rounded-lg p-4 max-h-96 overflow-y-auto">
                      <p className="text-gray-700 whitespace-pre-wrap">{selectedQuelle.volltext}</p>
                    </div>
                  </div>
                )}

                {selectedQuelle.quelle_url && (
                  <div className="flex gap-3">
                    <a
                      href={selectedQuelle.quelle_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-6 py-3 bg-navy text-white rounded-lg font-semibold hover:bg-navy-700 transition"
                    >
                      Original-Quelle öffnen →
                    </a>
                    <button
                      onClick={closeModal}
                      className="px-6 py-3 text-navy hover:bg-gray-100 rounded-lg transition font-semibold"
                    >
                      Schließen
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
