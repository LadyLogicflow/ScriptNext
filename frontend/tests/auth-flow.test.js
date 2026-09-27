/**
 * ScriptNext Sprint 2 Etappe 2a - Tests
 *
 * Test: API-Endpoints + Smoke-Tests
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "https://e1624faf90b9cb07.preview.w1009.pandora.cl01.efiniti.de/preview/wl0whd9a/scriptnext-backend";
const FRONTEND_BASE = "https://e1624faf90b9cb07.preview.w1009.pandora.cl01.efiniti.de/preview/wl0whd9a/scriptnext-frontend";

async function testAPIEndpoints() {
  console.log("🧪 Test: API-Endpoints erreichbar\n");

  // 1. Backend erreichbar (mit Login-Endpoint testen)
  console.log("1️⃣  Backend erreichbar testen...");

  // 2. Login-Endpoint (mit falschen Credentials = 401 erwartet)
  console.log("2️⃣  Login-Endpoint: POST /api/v1/auth/login (falsche Credentials)");
  const loginRes = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ benutzername: "test", passwort: "wrong" }),
  });

  if (loginRes.status !== 401) {
    throw new Error(`❌ Erwartete 401, bekam ${loginRes.status}`);
  }
  console.log("✅ Login-Endpoint erreichbar (401 wie erwartet)\n");

  // 3. Themen-Endpoint ohne Auth (401 erwartet)
  console.log("3️⃣  Themen-Endpoint: GET /api/v1/themen (ohne Auth)");
  const themenRes = await fetch(`${API_BASE}/api/v1/themen`);

  if (themenRes.status !== 401) {
    throw new Error(`❌ Erwartete 401, bekam ${themenRes.status}`);
  }
  console.log("✅ Themen-Endpoint geschützt (401 wie erwartet)\n");

  // 4. Logout-Endpoint
  console.log("4️⃣  Logout-Endpoint: POST /api/v1/auth/logout");
  const logoutRes = await fetch(`${API_BASE}/api/v1/auth/logout`, {
    method: "POST",
  });

  // Logout ohne Auth sollte auch funktionieren (idempotent)
  // 200 = OK, 204 = No Content, 401 = Unauthorized - alles valide
  if (logoutRes.status !== 200 && logoutRes.status !== 204 && logoutRes.status !== 401) {
    throw new Error(`❌ Logout-Endpoint nicht erreichbar: ${logoutRes.status}`);
  }
  console.log("✅ Logout-Endpoint erreichbar\n");

  console.log("🎉 API-Endpoints Test: BESTANDEN!\n");
}

async function runAllTests() {
  try {
    await testAPIEndpoints();
    console.log("✅✅✅ API-TESTS BESTANDEN! ✅✅✅");
    console.log("\n📝 Hinweis: Smoke-Tests (Frontend) in tests/smoke.test.js\n");
    process.exit(0);
  } catch (err) {
    console.error(`\n❌ TEST FEHLGESCHLAGEN:\n${err.message}\n`);
    process.exit(1);
  }
}

runAllTests();
