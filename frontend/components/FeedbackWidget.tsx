"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

type Bewertung = "gut" | "zu_langweilig" | "falsche_ebene";

type Props = {
  seminarId: number;
};

export default function FeedbackWidget({ seminarId }: Props) {
  const [bewertung, setBewertung] = useState<Bewertung | null>(null);
  const [kommentar, setKommentar] = useState("");
  const [zeigeDanke, setZeigeDanke] = useState(false);
  const [laedt, setLaedt] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);

  async function sendeFeedback(bewertungValue: Bewertung) {
    setBewertung(bewertungValue);
    setLaedt(true);
    setFehler(null);

    try {
      const res = await fetch(`${API_BASE}/api/v1/seminare/${seminarId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          bewertung: bewertungValue,
          kommentar: kommentar || undefined,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Feedback konnte nicht gespeichert werden" }));
        throw new Error(data.detail ?? "Feedback konnte nicht gespeichert werden");
      }

      setZeigeDanke(true);
      setLaedt(false);
    } catch (err) {
      setFehler(err instanceof Error ? err.message : "Fehler beim Senden");
      setLaedt(false);
    }
  }

  if (zeigeDanke) {
    return (
      <div className="bg-lime bg-opacity-20 border border-lime rounded-lg p-6 text-center">
        <p className="text-xl font-bold text-navy mb-2">✅ Vielen Dank für Ihr Feedback!</p>
        <p className="text-gray-700">Ihre Bewertung hilft uns, die Seminare zu verbessern.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-lg p-6">
      <h3 className="text-lg font-semibold text-navy mb-4">Wie fanden Sie das Seminar?</h3>

      {fehler && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
          <p className="text-red-600">{fehler}</p>
        </div>
      )}

      {/* 3-Buttons-Flow */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        <button
          onClick={() => sendeFeedback("gut")}
          disabled={laedt}
          className="px-6 py-4 bg-lime text-navy rounded-lg font-semibold hover:bg-lime-600 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          <span className="text-2xl">👍</span>
          <span>Gut geklappt!</span>
        </button>
        <button
          onClick={() => sendeFeedback("zu_langweilig")}
          disabled={laedt}
          className="px-6 py-4 bg-gray-100 text-gray-700 rounded-lg font-semibold hover:bg-gray-200 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          <span className="text-2xl">😴</span>
          <span>Zu langweilig</span>
        </button>
        <button
          onClick={() => sendeFeedback("falsche_ebene")}
          disabled={laedt}
          className="px-6 py-4 bg-gray-100 text-gray-700 rounded-lg font-semibold hover:bg-gray-200 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          <span className="text-2xl">🎯</span>
          <span>Falsche Ebene</span>
        </button>
      </div>

      {/* Optionales Textfeld */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Optionaler Kommentar:
        </label>
        <textarea
          value={kommentar}
          onChange={(e) => setKommentar(e.target.value)}
          maxLength={1000}
          rows={3}
          placeholder="Was können wir verbessern? (optional)"
          className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-lime outline-none resize-none"
        />
        <p className="text-xs text-gray-500 mt-1">{kommentar.length} / 1000 Zeichen</p>
      </div>

      {laedt && (
        <div className="flex items-center justify-center gap-2 text-gray-600 mt-4">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-navy"></div>
          <p>Sende Feedback...</p>
        </div>
      )}
    </div>
  );
}
