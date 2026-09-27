import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ScriptNext",
  description: "Dokumenten-Ingest und Themen-Extraktion",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="de">
      <body className="antialiased">{children}</body>
    </html>
  );
}
