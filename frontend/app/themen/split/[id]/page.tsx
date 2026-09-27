"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

type Chunk = {
  id: string; // UUID
  text: string;
};

type Thema = {
  id: number;
  titel: string;
  beschreibung: string;
  chunks: Chunk[];
};

export default function ThemenSplitPage() {
  const router = useRouter();
  const params = useParams();
  const themaId = parseInt(params.id as string);

  const [thema, setThema] = useState<Thema | null>(null);
  const [titel1, setTitel1] = useState("");
  const [titel2, setTitel2] = useState("");
  const [chunks1, setChunks1] = useState<string[]>([]); // UUID[]
  const [chunks2, setChunks2] = useState<string[]>([]); // UUID[]
  const [laedt, setLaedt] = useState(true);
  const [fehler, setFehler] = useState<string | null>(null);
  const [verarbeitet, setVerarbeitet] = useState(false);

  useEffect(() => {
    laden();
  }, [themaId]);

  async function laden() {
    try {
      // TODO: Echten Endpoint verwenden sobald Backend fertig
      // Erstmal Mock-Daten
      setThema({
        id: themaId,
        titel: "Beispiel-Thema",
        beschreibung: "Beschreibung des Themas",
        chunks: [
          { id: "uuid-1", text: "Chunk 1: Lorem ipsum dolor sit amet..." },
          { id: "uuid-2", text: "Chunk 2: Consectetur adipiscing elit..." },
          { id: "uuid-3", text: "Chunk 3: Sed do eiusmod tempor..." },
          { id: "uuid-4", text: "Chunk 4: Incididunt ut labore et dolore..." },
        ],
      });
      setLaedt(false);
    } catch (err) {
      setFehler("Thema konnte nicht geladen werden");
      setLaedt(false);
    }
  }

  async function handleSplit() {
    if (!titel1 || !titel2) {
      alert("Bitte beide Titel eingeben!");
      return;
    }

    if (chunks1.length === 0 || chunks2.length === 0) {
      alert("Bitte jedem Thema mindestens einen Chunk zuweisen!");
      return;
    }

    setVerarbeitet(true);

    try {
      const res = await fetch(`${API_BASE}/api/v1/themen/${themaId}/split`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          titel_a: titel1,
          titel_b: titel2,
          chunk_ids_a: chunks1, // Nur chunk_ids_a - Rest geht automatisch in thema_b
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Split fehlgeschlagen" }));
        throw new Error(data.detail ?? "Split fehlgeschlagen");
      }

      // Erfolg - zurück zu Themen-Liste
      router.push("/themen");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Split fehlgeschlagen");
      setVerarbeitet(false);
    }
  }

  function toggleChunk(chunkId: string, target: 1 | 2) {
    if (target === 1) {
      if (chunks1.includes(chunkId)) {
        setChunks1(chunks1.filter((id) => id !== chunkId));
      } else {
        setChunks1([...chunks1, chunkId]);
        setChunks2(chunks2.filter((id) => id !== chunkId));
      }
    } else {
      if (chunks2.includes(chunkId)) {
        setChunks2(chunks2.filter((id) => id !== chunkId));
      } else {
        setChunks2([...chunks2, chunkId]);
        setChunks1(chunks1.filter((id) => id !== chunkId));
      }
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

  if (laedt) {
    return (
      <main className="min-h-screen bg-gradient-to-b from-white to-gray-50 p-4">
        <div className="max-w-6xl mx-auto pt-6">
          <p className="text-gray-500">Lädt...</p>
        </div>
      </main>
    );
  }

  if (fehler || !thema) {
    return (
      <main className="min-h-screen bg-gradient-to-b from-white to-gray-50 p-4">
        <div className="max-w-6xl mx-auto pt-6">
          <p className="text-red-600">{fehler || "Thema nicht gefunden"}</p>
          <Link href="/themen" className="text-navy hover:underline mt-4 inline-block">
            Zurück zu Themen
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-b from-white to-gray-50 p-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8 pt-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-navy rounded-xl">
              <svg className="w-8 h-8 text-lime" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
              </svg>
            </div>
            <div>
              <h1 className="text-2xl font-bold text-navy">ScriptNext</h1>
              <p className="text-gray-600 text-sm">Thema aufteilen</p>
            </div>
          </div>
          <div className="flex gap-3">
            <Link
              href="/themen"
              className="px-4 py-2 text-navy hover:bg-gray-100 rounded-lg transition font-medium"
            >
              Abbrechen
            </Link>
            <button
              onClick={handleLogout}
              className="px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition font-medium"
            >
              Abmelden
            </button>
          </div>
        </div>

        {/* Original-Thema */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <h2 className="text-lg font-semibold text-navy mb-2">Original-Thema:</h2>
          <p className="text-xl font-bold text-gray-800">{thema.titel}</p>
          <p className="text-sm text-gray-600 mt-1">{thema.beschreibung}</p>
        </div>

        {/* Split-Formular */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Thema 1 */}
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h3 className="text-lg font-semibold text-navy mb-4">Neues Thema 1</h3>
            <input
              type="text"
              value={titel1}
              onChange={(e) => setTitel1(e.target.value)}
              placeholder="Titel für Thema 1"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-lime outline-none mb-4"
            />
            <div className="text-sm text-gray-600 mb-2">
              Zugewiesene Chunks: {chunks1.length}
            </div>
          </div>

          {/* Thema 2 */}
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h3 className="text-lg font-semibold text-navy mb-4">Neues Thema 2</h3>
            <input
              type="text"
              value={titel2}
              onChange={(e) => setTitel2(e.target.value)}
              placeholder="Titel für Thema 2"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-lime outline-none mb-4"
            />
            <div className="text-sm text-gray-600 mb-2">
              Zugewiesene Chunks: {chunks2.length}
            </div>
          </div>
        </div>

        {/* Chunks */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <h3 className="text-lg font-semibold text-navy mb-4">
            Chunks zuweisen (klicken Sie auf die Buttons)
          </h3>
          <div className="space-y-3">
            {thema.chunks.map((chunk) => (
              <div
                key={chunk.id}
                className="border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition"
              >
                <p className="text-sm text-gray-700 mb-3">{chunk.text}</p>
                <div className="flex gap-2">
                  <button
                    onClick={() => toggleChunk(chunk.id, 1)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                      chunks1.includes(chunk.id)
                        ? "bg-navy text-white"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                    }`}
                  >
                    {chunks1.includes(chunk.id) ? "✓ Thema 1" : "→ Thema 1"}
                  </button>
                  <button
                    onClick={() => toggleChunk(chunk.id, 2)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                      chunks2.includes(chunk.id)
                        ? "bg-lime text-navy"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                    }`}
                  >
                    {chunks2.includes(chunk.id) ? "✓ Thema 2" : "→ Thema 2"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Submit-Button */}
        <div className="flex justify-end">
          <button
            onClick={handleSplit}
            disabled={verarbeitet || !titel1 || !titel2 || chunks1.length === 0 || chunks2.length === 0}
            className="px-8 py-3 bg-navy text-white rounded-lg font-semibold hover:bg-navy-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {verarbeitet ? "Verarbeite..." : "Thema aufteilen"}
          </button>
        </div>
      </div>
    </main>
  );
}
