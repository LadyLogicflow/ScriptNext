/**
 * ScriptNext Sprint 3 Etappe 3b - Rechtsquellen Smoke Test
 *
 * Test: Rechtsquellen-Page rendert
 */

const BASE_URL = "http://localhost:3000";

async function testRechtsquellenPage() {
  console.log("🧪 Smoke Test: Rechtsquellen-Page\n");

  // Test: Rechtsquellen-Page rendert
  console.log("1️⃣  GET /rechtsquellen");
  const res = await fetch(`${BASE_URL}/rechtsquellen`);

  if (!res.ok) {
    throw new Error(`❌ Rechtsquellen-Page rendert nicht! Status: ${res.status}`);
  }

  const contentType = res.headers.get("content-type");
  if (!contentType?.includes("text/html")) {
    throw new Error(`❌ Rechtsquellen-Page ist kein HTML! Content-Type: ${contentType}`);
  }

  const html = await res.text();
  if (!html.includes("Rechtsquellen-Übersicht") && !html.includes("Rechtsquellen")) {
    throw new Error("❌ Rechtsquellen-Page hat nicht den erwarteten Content!");
  }

  console.log("✅ Rechtsquellen-Page rendert erfolgreich\n");
  console.log("✅✅✅ RECHTSQUELLEN SMOKE TEST BESTANDEN! ✅✅✅\n");
  process.exit(0);
}

// Kleine Wartezeit damit der Server ready ist
setTimeout(testRechtsquellenPage, 2000);
