"""
test_armoriq_intent_assurance.py — ArmorIQ Intent Assurance Test Suite
======================================================================
Tests:
1. armoriq_guard unit tests (threshold policy, SHA-256 signature verification).
2. POST /api/studio/intercept_alert returns armoriq_intent_id.
3. Policy enforcement: risk_score < 0.75 is blocked by circuit breaker (403).
4. POST /api/studio/armoriq/verify validates TERMINATE_CALL and returns AIQ-* intent ID.
"""

import sys
from demo_server import app
from services.armoriq_guard import armoriq

# Windows CP1252 safety
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def run_tests():
    print("=" * 65)
    print("[TEST] ArmorIQ Intent Assurance & Circuit-Breaker Verification")
    print("=" * 65)

    # 1. Unit Test: Policy Thresholds
    print("\n--- TEST 1: armoriq_guard Policy Threshold Checks ---")
    auth_res = armoriq.verify_action_intent("TERMINATE_CALL", risk_score=0.94)
    print(f"  TERMINATE_CALL (0.94): authorized={auth_res['authorized']}, intent_id={auth_res['intent_id']}")
    assert auth_res["authorized"] is True
    assert auth_res["intent_id"].startswith("AIQ-")
    assert armoriq.verify_receipt_signature(auth_res) is True

    blocked_res = armoriq.verify_action_intent("TERMINATE_CALL", risk_score=0.60)
    print(f"  TERMINATE_CALL (0.60): authorized={blocked_res['authorized']}, intent_id={blocked_res['intent_id']}")
    assert blocked_res["authorized"] is False
    assert blocked_res["status"] == "POLICY_REJECTED"
    print("  [PASS] Policy checks (>= 0.75 threshold) & SHA-256 signatures verified.")

    # 2. Flask Test Client
    client = app.test_client()

    print("\n--- TEST 2: POST /api/studio/intercept_alert (Authorized with Intent ID) ---")
    payload = {
        "text": "Security Alert: Dhwani Kavach Shield has detected a synthetic voice clone.",
        "risk_score": 0.94
    }
    res = client.post("/api/studio/intercept_alert", json=payload)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.get_json()
    intent_id = data.get("armoriq_intent_id")
    print(f"  Returned armoriq_intent_id: {intent_id}")
    assert intent_id is not None
    assert intent_id.startswith("AIQ-")
    print("  [PASS] /api/studio/intercept_alert returned cryptographic armoriq_intent_id.")

    print("\n--- TEST 3: POST /api/studio/intercept_alert Policy Rejection (< 0.75) ---")
    blocked_payload = {
        "text": "Harmless greeting",
        "risk_score": 0.50
    }
    blocked_res = client.post("/api/studio/intercept_alert", json=blocked_payload)
    assert blocked_res.status_code == 403, f"Expected 403, got {blocked_res.status_code}"
    blocked_data = blocked_res.get_json()
    print(f"  Rejection response: error='{blocked_data.get('error')}'")
    assert blocked_data.get("ok") is False
    assert blocked_data.get("armoriq_intent_id").startswith("AIQ-")
    print("  [PASS] Below-threshold action rejected with 403 under ArmorIQ governance.")

    print("\n--- TEST 4: POST /api/studio/armoriq/verify (TERMINATE_CALL) ---")
    term_payload = {
        "action": "TERMINATE_CALL",
        "risk_score": 0.94,
        "context": {"source": "interceptor_modal", "call_id": "call_12345"}
    }
    term_res = client.post("/api/studio/armoriq/verify", json=term_payload)
    assert term_res.status_code == 200
    term_data = term_res.get_json()
    print(f"  Action: TERMINATE_CALL -> Intent ID: {term_data.get('armoriq_intent_id')}, Authorized: {term_data.get('authorized')}")
    assert term_data.get("ok") is True
    assert term_data.get("authorized") is True
    assert term_data.get("armoriq_intent_id").startswith("AIQ-")
    print("  [PASS] /api/studio/armoriq/verify confirmed intent authorization.")

    print("\n" + "=" * 65)
    print("[DONE] ALL ARMORIQ INTENT ASSURANCE TESTS PASSED (4/4).")
    print("=" * 65)
    return True

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

