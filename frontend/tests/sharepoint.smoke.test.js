/**
 * ScriptNext Sprint 3 Etappe 3a - SharePoint Smoke Test
 *
 * Test: SharePoint-Page rendert
 */

const BASE_URL = "http://localhost:3000";

async function testSharePointPage() {
  console.log("🧪 Smoke Test: SharePoint-Page\n");

  // Test: SharePoint-Page rendert
  console.log("1️⃣  GET /sharepoint");
  const res = await fetch(`${BASE_URL}/sharepoint`);

  if (!res.ok) {
    throw new Error(`❌ SharePoint-Page rendert nicht! Status: ${res.status}`);
  }

  const contentType = res.headers.get("content-type");
  if (!contentType?.includes("text/html")) {
    throw new Error(`❌ SharePoint-Page ist kein HTML! Content-Type: ${contentType}`);
  }

  const html = await res.text();
  if (!html.includes("SharePoint verbinden") && !html.includes("SharePoint-Anbindung")) {
    throw new Error("❌ SharePoint-Page hat nicht den erwarteten Content!");
  }

  console.log("✅ SharePoint-Page rendert erfolgreich\n");
  console.log("✅✅✅ SHAREPOINT SMOKE TEST BESTANDEN! ✅✅✅\n");
  process.exit(0);
}

// Kleine Wartezeit damit der Server ready ist
setTimeout(testSharePointPage, 2000);
