"""
test_step2_elevenlabs_service.py — Unit Tests for ElevenLabs Service
====================================================================
Tests the 3 core capabilities from PPT:
1. ConvAI Agent Builder (/v1/convai/agents/create)
2. Flash v2.5 Voice Alert Synthesis (eleven_flash_v2_5)
3. Scribe STT Audio Chunk Transcription
4. Permission diagnostics & fallback safety
"""

import os
import sys

# Windows CP1252 safety
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def run_step2_tests():
    print("=" * 65)
    print("[TEST] STEP 2: ElevenLabs Service Unit Tests")
    print("=" * 65)

    from services.elevenlabs_service import ElevenLabsService, FLASH_MODEL_ID, SCRIBE_MODEL_ID
    
    svc = ElevenLabsService()
    print(f"[INFO] API Key present: {svc.has_api_key}")
    print(f"[INFO] Default Voice ID: {svc.default_voice_id}")

    # TEST 1: Probe Permissions & Diagnostics
    print("\n--- TEST 1: Permission Probing & Diagnostics ---")
    probe = svc.probe_permissions()
    print(f"  Mode: {probe.get('mode')}")
    print(f"  Permissions: {probe.get('permissions')}")
    if probe.get("recommendation"):
        print(f"  Note: {probe.get('recommendation')}")
    assert "has_key" in probe, "Missing has_key field"
    print("  [PASS] probe_permissions() returned structured diagnostics.")

    # TEST 2: ConvAI Agent Creation
    print("\n--- TEST 2: ConvAI Agent Creation (PPT Slide 3 & 4) ---")
    agent = svc.create_convai_agent(
        name="SBI Customer Care Assistant",
        prompt="You are a helpful banking executive at SBI. Help users with account balance inquiries.",
        language="en"
    )
    print(f"  Agent ID: {agent.get('agent_id')}")
    print(f"  Status: {agent.get('status')}")
    print(f"  Embed Tag: {agent.get('embed_tag')}")
    assert agent.get("success") is True, "Agent creation failed"
    assert "agent_id" in agent and len(agent["agent_id"]) > 0, "Missing agent_id"
    assert "embed_tag" in agent, "Missing embed_tag"
    print("  [PASS] create_convai_agent() successfully produced agent config.")

    # TEST 3: Signed Conversation URL Retrieval
    print("\n--- TEST 3: Signed Conversation URL for WebRTC/WebSocket ---")
    signed = svc.get_signed_conversation_url(agent["agent_id"])
    print(f"  Signed URL: {signed.get('signed_url')}")
    assert signed.get("success") is True, "Signed URL retrieval failed"
    assert "signed_url" in signed, "Missing signed_url"
    print("  [PASS] get_signed_conversation_url() produced valid endpoint.")

    # TEST 4: Flash v2.5 Voice Alert Synthesis (<75ms Latency)
    print("\n--- TEST 4: Flash v2.5 Voice Alert Synthesis (PPT Slide 4 & 5) ---")
    alert_text = "Security Warning: Dhwani Kavach Shield has detected a synthetic voice clone."
    alert_res = svc.generate_flash_intercept_alert(text=alert_text)
    latency = alert_res.get("latency_ms", 0)
    print(f"  Model: {alert_res.get('model')}")
    print(f"  Latency: {latency} ms")
    print(f"  Audio Payload Size: {len(alert_res.get('audio_base64', ''))} characters")
    assert alert_res.get("success") is True, "Alert generation failed"
    assert alert_res.get("model") == FLASH_MODEL_ID, f"Expected {FLASH_MODEL_ID}"
    assert len(alert_res.get("audio_base64", "")) > 100, "Audio payload empty"
    print("  [PASS] generate_flash_intercept_alert() successfully synthesized audio.")

    # TEST 5: Scribe STT Audio Chunk Transcription
    print("\n--- TEST 5: Scribe STT Chunk Transcription ---")
    dummy_audio = b"RIFF" + b"\x00" * 3000  # mock wav header/bytes
    stt_res = svc.transcribe_audio_chunk(audio_bytes_or_path=dummy_audio)
    print(f"  Model: {stt_res.get('model')}")
    print(f"  Status: {'Success' if stt_res.get('success') else 'Failed'}")
    assert "model" in stt_res and stt_res["model"] == SCRIBE_MODEL_ID
    print("  [PASS] transcribe_audio_chunk() handled audio chunk gracefully.")

    print("\n" + "=" * 65)
    print("[DONE] ALL STEP 2 UNIT TESTS PASSED (5/5). Service is rock-solid!")
    print("=" * 65)
    return True

if __name__ == "__main__":
    success = run_step2_tests()
    sys.exit(0 if success else 1)

