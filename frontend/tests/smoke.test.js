/**
 * ScriptNext Sprint 2 Etappe 2a - Smoke Tests
 *
 * Test: Seiten rendern (OHNE Backend)
 */

const BASE_URL = "http://localhost:3000";

async function testPageRenders(path, pageName) {
  console.log(`🧪 Test: ${pageName} rendert`);

  const res = await fetch(`${BASE_URL}${path}`);

  if (!res.ok && res.status !== 302) {
    throw new Error(`❌ ${pageName} rendert nicht! Status: ${res.status}`);
  }

  const contentType = res.headers.get("content-type");
  if (!contentType?.includes("text/html")) {
    throw new Error(`❌ ${pageName} ist kein HTML! Content-Type: ${contentType}`);
  }

  console.log(`✅ ${pageName} rendert erfolgreich (${res.status})\n`);
}

async function runSmokeTests() {
  console.log("🧪 SMOKE TESTS - Seiten-Rendering (OHNE Backend)\n");
  console.log("Teste gegen: " + BASE_URL + "\n");

  try {
    // Test 1: Login-Page
    await testPageRenders("/", "Login-Page (/)");

    // Test 2: Upload-Page (kann 302 redirect sein wenn nicht eingeloggt)
    await testPageRenders("/upload", "Upload-Page (/upload)");

    // Test 3: Themen-Page (kann 302 redirect sein wenn nicht eingeloggt)
    await testPageRenders("/themen", "Themen-Page (/themen)");

    console.log("✅✅✅ ALLE SMOKE TESTS BESTANDEN! ✅✅✅");
    console.log("\n📝 Hinweis: Diese Tests prüfen NUR ob die Seiten rendern.");
    console.log("📝 Backend/API-Tests kommen später wenn Backend läuft.\n");
    process.exit(0);
  } catch (err) {
    console.error(`\n❌ SMOKE TEST FEHLGESCHLAGEN:\n${err.message}\n`);
    process.exit(1);
  }
}

// Kleine Wartezeit damit der Server ready ist
setTimeout(runSmokeTests, 2000);
