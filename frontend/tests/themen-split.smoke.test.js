/**
 * ScriptNext Sprint 2 Etappe 2b - Themen-Split Smoke Test
 *
 * Test: Themen-Split-Page rendert
 */

const BASE_URL = "http://localhost:3000";

async function testThemenSplitPage() {
  console.log("🧪 Smoke Test: Themen-Split-Page\n");

  // Test: Themen-Split-Page mit ID rendert
  console.log("1️⃣  GET /themen/split/1");
  const res = await fetch(`${BASE_URL}/themen/split/1`);

  if (!res.ok) {
    throw new Error(`❌ Themen-Split-Page rendert nicht! Status: ${res.status}`);
  }

  const contentType = res.headers.get("content-type");
  if (!contentType?.includes("text/html")) {
    throw new Error(`❌ Themen-Split-Page ist kein HTML! Content-Type: ${contentType}`);
  }

  const html = await res.text();
  if (!html.includes("Thema aufteilen")) {
    throw new Error("❌ Themen-Split-Page hat nicht den erwarteten Content!");
  }

  console.log("✅ Themen-Split-Page rendert erfolgreich\n");
  console.log("✅✅✅ THEMEN-SPLIT SMOKE TEST BESTANDEN! ✅✅✅\n");
  process.exit(0);
}

// Kleine Wartezeit damit der Server ready ist
setTimeout(testThemenSplitPage, 2000);
