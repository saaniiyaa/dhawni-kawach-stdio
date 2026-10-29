"""
test_step3_backend_routes.py — Automated Route Verification Tests
==================================================================
Tests:
1. Baseline health & existing routes (/api/ping, /api/context, /api/voiceprints)
2. New Studio Permissions Endpoint: GET /api/studio/permissions
3. New ConvAI Agent Creation: POST /api/studio/agent/create
4. New Agent Signed URL: GET /api/studio/agent/signed_url
5. New Flash v2.5 Intercept Alert: POST /api/studio/intercept_alert
6. Negative tests (validation error handling)
"""

import json
import os
import sys

# Windows CP1252 safety
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def run_route_tests():
    print("=" * 65)
    print("[TEST] STEP 3: Backend Routes & Integration Verification")
    print("=" * 65)

    from demo_server import app
    client = app.test_client()

    # ── 1. BASELINE ROUTE CHECKS ──────────────────────────────────────────────
    print("\n--- TEST 1: Baseline Existing Routes ---")
    ping_res = client.get("/api/ping")
    assert ping_res.status_code == 200, f"Expected 200, got {ping_res.status_code}"
    ping_data = ping_res.get_json()
    print(f"  /api/ping: status={ping_data.get('status')}, model={ping_data.get('model')}")
    assert ping_data.get("ok") is True

    context_res = client.post("/api/context", json={"number": "1800112211"})
    assert context_res.status_code == 200
    ctx_data = context_res.get_json()
    print(f"  /api/context (SBI helpline): level={ctx_data.get('level')}")
    assert ctx_data.get("level") == "safe"
    print("  [PASS] Existing baseline routes are fully operational.")

    # ── 2. STUDIO PERMISSIONS ENDPOINT ────────────────────────────────────────
    print("\n--- TEST 2: GET /api/studio/permissions ---")
    perm_res = client.get("/api/studio/permissions")
    assert perm_res.status_code == 200, f"Permissions endpoint failed with {perm_res.status_code}"
    perm_data = perm_res.get_json()
    print(f"  ok: {perm_data.get('ok')}")
    print(f"  mode: {perm_data.get('mode')}")
    print(f"  permissions: {perm_data.get('permissions')}")
    assert perm_data.get("ok") is True
    assert "permissions" in perm_data
    print("  [PASS] /api/studio/permissions responded with live diagnostics.")

    # ── 3. STUDIO CONVAI AGENT CREATION ───────────────────────────────────────
    print("\n--- TEST 3: POST /api/studio/agent/create ---")
    agent_payload = {
        "name": "SBI Loan Assistance Bot",
        "prompt": "You are a courteous banking assistant helping users check home loan interest rates.",
        "first_message": "Namaste! Welcome to SBI Loan Support. How may I help you?",
        "language": "en"
    }
    create_res = client.post("/api/studio/agent/create", json=agent_payload)
    assert create_res.status_code == 200, f"Create agent failed with {create_res.status_code}: {create_res.text}"
    create_data = create_res.get_json()
    agent_id = create_data.get("agent_id")
    print(f"  Created Agent ID: {agent_id}")
    print(f"  Status: {create_data.get('status')}")
    print(f"  Model: {create_data.get('model')}")
    print(f"  Embed Tag: {create_data.get('embed_tag')}")
    assert create_data.get("ok") is True
    assert agent_id and len(agent_id) > 0
    print("  [PASS] /api/studio/agent/create deployed agent successfully.")

    # ── 4. STUDIO AGENT SIGNED URL ────────────────────────────────────────────
    print("\n--- TEST 4: GET /api/studio/agent/signed_url ---")
    signed_res = client.get(f"/api/studio/agent/signed_url?agent_id={agent_id}")
    assert signed_res.status_code == 200, f"Signed URL failed with {signed_res.status_code}"
    signed_data = signed_res.get_json()
    print(f"  Signed URL: {signed_data.get('signed_url')}")
    assert signed_data.get("ok") is True
    assert "signed_url" in signed_data
    print("  [PASS] /api/studio/agent/signed_url returned active session endpoint.")

    # ── 5. STUDIO FLASH v2.5 INTERCEPT ALERT ──────────────────────────────────
    print("\n--- TEST 5: POST /api/studio/intercept_alert (Flash v2.5) ---")
    alert_payload = {
        "text": "Security Alert: Dhwani Kavach Shield has detected an unauthorized synthetic voice clone. Call is held for identity verification."
    }
    alert_res = client.post("/api/studio/intercept_alert", json=alert_payload)
    assert alert_res.status_code == 200, f"Alert endpoint failed with {alert_res.status_code}"
    alert_data = alert_res.get_json()
    print(f"  Model: {alert_data.get('model')}")
    print(f"  Latency: {alert_data.get('latency_ms')} ms")
    print(f"  Audio Payload Size: {len(alert_data.get('audio_base64', ''))} characters")
    assert alert_data.get("ok") is True
    assert alert_data.get("model") == "eleven_flash_v2_5"
    assert len(alert_data.get("audio_base64", "")) > 100
    print("  [PASS] /api/studio/intercept_alert delivered Flash v2.5 audio warning.")

    # ── 6. NEGATIVE VALIDATION TEST ───────────────────────────────────────────
    print("\n--- TEST 6: Input Validation ---")
    bad_res = client.post("/api/studio/agent/create", json={"prompt": ""})
    assert bad_res.status_code == 400, f"Expected 400 for empty prompt, got {bad_res.status_code}"
    print(f"  Empty prompt rejected cleanly with 400: {bad_res.get_json().get('error')}")
    print("  [PASS] Input validation guards working.")

    print("\n" + "=" * 65)
    print("[DONE] ALL STEP 3 BACKEND ROUTE TESTS PASSED (6/6).")
    print("=" * 65)
    return True

if __name__ == "__main__":
    success = run_route_tests()
    sys.exit(0 if success else 1)

