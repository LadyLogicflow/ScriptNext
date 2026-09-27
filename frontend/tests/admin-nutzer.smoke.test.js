/**
 * ScriptNext Sprint 3 Etappe 3d - Admin Nutzer-Verwaltung Smoke Test
 *
 * Test: Admin Nutzer-Page rendert
 */

const BASE_URL = "http://localhost:3000";

async function testAdminNutzerPage() {
  console.log("🧪 Smoke Test: Admin Nutzer-Page\n");

  // Test: Admin Nutzer-Page rendert
  console.log("1️⃣  GET /admin/nutzer");
  const res = await fetch(`${BASE_URL}/admin/nutzer`);

  if (!res.ok) {
    throw new Error(`❌ Admin Nutzer-Page rendert nicht! Status: ${res.status}`);
  }

  const contentType = res.headers.get("content-type");
  if (!contentType?.includes("text/html")) {
    throw new Error(`❌ Admin Nutzer-Page ist kein HTML! Content-Type: ${contentType}`);
  }

  const html = await res.text();
  if (!html.includes("Nutzer-Verwaltung") && !html.includes("ScriptNext Admin")) {
    throw new Error("❌ Admin Nutzer-Page hat nicht den erwarteten Content!");
  }

  console.log("✅ Admin Nutzer-Page rendert erfolgreich\n");
  console.log("✅✅✅ ADMIN NUTZER SMOKE TEST BESTANDEN! ✅✅✅\n");
  process.exit(0);
}

// Kleine Wartezeit damit der Server ready ist
setTimeout(testAdminNutzerPage, 2000);
