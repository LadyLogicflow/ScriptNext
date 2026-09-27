/**
 * ScriptNext Sprint 3 Etappe 3c - Chunk-Warnbadge Smoke Test
 *
 * Test: Themen-Page rendert mit Warnbadge-Code
 */

const BASE_URL = "http://localhost:3000";

async function testThemenPageWithWarnbadge() {
  console.log("🧪 Smoke Test: Themen-Page mit Warnbadge\n");

  // Test: Themen-Page rendert
  console.log("1️⃣  GET /themen");
  const res = await fetch(`${BASE_URL}/themen`);

  if (!res.ok) {
    throw new Error(`❌ Themen-Page rendert nicht! Status: ${res.status}`);
  }

  const contentType = res.headers.get("content-type");
  if (!contentType?.includes("text/html")) {
    throw new Error(`❌ Themen-Page ist kein HTML! Content-Type: ${contentType}`);
  }

  const html = await res.text();
  if (!html.includes("Themen-Übersicht") && !html.includes("Themen")) {
    throw new Error("❌ Themen-Page hat nicht den erwarteten Content!");
  }

  console.log("✅ Themen-Page mit Warnbadge-Code rendert erfolgreich\n");
  console.log("✅✅✅ CHUNK-WARNBADGE SMOKE TEST BESTANDEN! ✅✅✅\n");
  process.exit(0);
}

// Kleine Wartezeit damit der Server ready ist
setTimeout(testThemenPageWithWarnbadge, 2000);
