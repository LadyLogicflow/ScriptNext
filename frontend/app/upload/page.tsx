"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

type UploadStatus = {
  status: "pending" | "processing" | "completed" | "failed";
  themen_anzahl?: number;
  error_message?: string;
};

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dokumentId, setDokumentId] = useState<number | null>(null);
  const [status, setStatus] = useState<UploadStatus | null>(null);
  const [fehler, setFehler] = useState<string | null>(null);

  // Cookie-basierte Auth - kein Check mehr nötig
  // Falls nicht eingeloggt, gibt Backend 401 zurück

  useEffect(() => {
    // Poll status if dokumentId exists
    if (!dokumentId) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/v1/dokumente/${dokumentId}`, {
          credentials: "include",
        });

        if (res.ok) {
          const data: UploadStatus = await res.json();
          setStatus(data);

          if (data.status === "completed") {
            clearInterval(interval);
            // Redirect to themen page after 2 seconds
            setTimeout(() => router.push("/themen"), 2000);
          } else if (data.status === "failed") {
            clearInterval(interval);
          }
        }
      } catch (err) {
        console.error("Status-Polling fehlgeschlagen", err);
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(interval);
  }, [dokumentId, router]);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;

    setFehler(null);
    setUploading(true);

    try {
      const formData = new FormData();
      formData.append("datei", file);

      const res = await fetch(`${API_BASE}/api/v1/upload`, {
        method: "POST",
        credentials: "include",
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Upload fehlgeschlagen" }));
        setFehler(data.detail ?? "Upload fehlgeschlagen");
        setUploading(false);
        return;
      }

      const data = await res.json();
      setDokumentId(data.dokument_id);
      // Start polling
    } catch (err) {
      setFehler("Verbindung fehlgeschlagen. Bitte später erneut versuchen.");
      setUploading(false);
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
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8 pt-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-navy rounded-xl">
              <svg className="w-8 h-8 text-lime" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div>
              <h1 className="text-2xl font-bold text-navy">ScriptNext</h1>
              <p className="text-gray-600 text-sm">Dokument hochladen</p>
            </div>
          </div>
          <div className="flex gap-3">
            <Link
              href="/themen"
              className="px-4 py-2 text-navy hover:bg-gray-100 rounded-lg transition font-medium"
            >
              Themen ansehen
            </Link>
            <button
              onClick={handleLogout}
              className="px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition font-medium"
            >
              Abmelden
            </button>
          </div>
        </div>

        {/* Upload-Formular */}
        <div className="bg-white rounded-xl shadow-lg p-8">
          <h2 className="text-xl font-semibold text-navy mb-6">Dokument hochladen</h2>

          {fehler && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm mb-6">
              {fehler}
            </div>
          )}

          {status && (
            <div className={`px-4 py-3 rounded-lg text-sm mb-6 ${
              status.status === "completed" ? "bg-green-50 border border-green-200 text-green-700" :
              status.status === "failed" ? "bg-red-50 border border-red-200 text-red-700" :
              "bg-blue-50 border border-blue-200 text-blue-700"
            }`}>
              {status.status === "pending" && "Dokument wird vorbereitet..."}
              {status.status === "processing" && "Dokument wird verarbeitet..."}
              {status.status === "completed" && `Dokument erfolgreich verarbeitet! ${status.themen_anzahl ?? 0} Themen gefunden. Weiterleitung...`}
              {status.status === "failed" && `Verarbeitung fehlgeschlagen: ${status.error_message ?? "Unbekannter Fehler"}`}
            </div>
          )}

          <form onSubmit={handleUpload} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Datei auswählen
              </label>
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-lime transition">
                <input
                  type="file"
                  accept=".pdf,.doc,.docx,.txt"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  disabled={uploading || !!dokumentId}
                  className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-navy file:text-white hover:file:bg-navy-700 file:cursor-pointer"
                />
                {file && (
                  <p className="mt-2 text-sm text-gray-600">Ausgewählt: {file.name}</p>
                )}
              </div>
            </div>

            <button
              type="submit"
              disabled={!file || uploading || !!dokumentId}
              className="w-full bg-navy text-white py-3 px-6 rounded-lg font-semibold hover:bg-navy-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {uploading || dokumentId ? "Wird hochgeladen..." : "Hochladen"}
            </button>
          </form>
        </div>
      </div>
    </main>
  );
}
