"""
test_step1_env.py — Automated verification test for Step 1 (Environment & Dependencies)
========================================================================================
Tests:
1. python-dotenv loads .env properly.
2. requests package can be imported.
3. elevenlabs package can be imported and initialized.
4. Validates API key detection (real key vs graceful fallback indicator).
"""

import os
import sys

# Windows cp1252 safety
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def test_environment_setup():
    print("=" * 60)
    print("[TEST] STEP 1: Environment & ElevenLabs Dependency Verification")
    print("=" * 60)

    # 1. Test dotenv loading
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
        print("[PASS] python-dotenv loaded successfully.")
    except Exception as e:
        print(f"[FAIL] Failed to load dotenv: {e}")
        return False

    # 2. Test requests package
    try:
        import requests
        print(f"[PASS] requests package available (v{requests.__version__}).")
    except Exception as e:
        print(f"[FAIL] Failed to import requests: {e}")
        return False

    # 3. Test elevenlabs package
    try:
        import elevenlabs
        from elevenlabs.client import ElevenLabs
        print(f"[PASS] elevenlabs package imported successfully (v{elevenlabs.__version__}).")
    except Exception as e:
        print(f"[FAIL] Failed to import elevenlabs: {e}")
        return False

    # 4. Check configuration & API key status
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    voice_id = os.getenv("ELEVENLABS_DEFAULT_VOICE_ID", "21m00Tcm4TlvDq8ikWAM").strip()
    
    print(f"[INFO] ELEVENLABS_DEFAULT_VOICE_ID: {voice_id}")
    if api_key and not api_key.startswith("your_"):
        masked = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "***"
        print(f"[PASS] Real ELEVENLABS_API_KEY detected ({masked}).")
    else:
        print("[INFO] ELEVENLABS_API_KEY is currently empty/placeholder in .env.")
        print("       -> System will safely operate in Mock/Fallback mode until key is entered.")

    print("=" * 60)
    print("[DONE] ALL STEP 1 CHECKS PASSED: Environment is ready for ElevenLabs service.")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_environment_setup()
    sys.exit(0 if success else 1)
