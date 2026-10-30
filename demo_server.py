# demo_server.py  (v2 - full demo: call screen, context card, voiceprint, radar)
# DHWANI-KAVACH LIVE DEMO SERVER

import math
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import json
import tempfile

try:
    from flask import Flask, request, jsonify, send_file, make_response
except ImportError:
    print("flask is not installed. Run 0c_install_flask.py once, then run this.")
    raise SystemExit(0)

import numpy as np
import torch

from ml.audio.io import load, SR, fix_length, energy_vad
from ml.features.dsp import logmel
from ml.models.cnn import MelCNN
from ml.engine.temporal import TemporalEngine, EngineConfig, policy_for
from ml.engine.scam_radar import scan
from ml.engine import voiceprint_falak
from ml.augment.codecs import FFMPEG, run_quiet

torch.set_num_threads(1)

MODEL_PATH, MODEL_NAME = None, None
for cand, name in [("results/cnn_v2/model.pt", "CNN v2 (codec-hardened)"),
                   ("results/cnn_v1/model.pt", "CNN v1 (clean-trained)")]:
    if os.path.exists(cand):
        MODEL_PATH, MODEL_NAME = cand, name
        break
if MODEL_PATH is None:
    print("No trained model found (results/cnn_v1 or cnn_v2).")
    print("Run 7_train_cnn.py first, then start the demo.")
    raise SystemExit(0)

model = MelCNN()
model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu"))
model.eval()
print("demo model:", MODEL_NAME, "<-", MODEL_PATH)

# ---- Block 10 calibration: thresholds + silence gate ----
_CAL_PATH = os.path.join("results", "calibration.json")
CAL = json.load(open(_CAL_PATH)) if os.path.exists(_CAL_PATH) else {}
engine = TemporalEngine(EngineConfig(
    theta_lo=float(CAL.get("theta_lo", 0.62)),
    theta_hi=float(CAL.get("theta_hi", 0.90)),
))
if CAL:
    print(f"calibration: loaded {_CAL_PATH} "
          f"(vad_min={CAL.get('vad_min')}, bias={CAL.get('logit_bias')}, "
          f"theta {CAL.get('theta_lo')}/{CAL.get('theta_hi')})")
else:
    print("calibration: none found - DEFAULTS (run 14_block10_calibrate.py)")
SECONDS = 4.0

# ---- demo whitelist of OFFICIAL helpline numbers ----
OFFICIAL_NUMBERS = {
    # national helplines (publicly published)
    "1930": "National Cyber Crime Helpline",
    "112":  "National Emergency Number",
    "100":  "Police",
    "108":  "Ambulance Service",
    "1091": "Women Helpline",
    "1098": "Child Helpline (Childline)",
    "139":  "Rail Madad - Indian Railways",
    "1906": "LPG Emergency Helpline",
    "1909": "TRAI DND / Telemarketing Complaints",
    "1947": "UIDAI / Aadhaar Helpline",
    "14567": "Elder Line - Senior Citizens",
    "198":  "Telecom Customer Care (all operators)",
    # major banks - officially published customer-care numbers
    "1800112211": "State Bank of India - customer care",
    "1800227222": "HDFC Bank - customer care",
    "18001024242": "ICICI Bank - customer care",
    "18004195000": "Axis Bank - customer care",
    "18602662666": "Kotak Mahindra Bank - customer care",
    "18001802222": "Punjab National Bank - customer care",
    "1800223344": "Bank of Baroda - customer care",
    "1800222244": "Union Bank of India - customer care",
    "18004250018": "Canara Bank - customer care",
    "18605001111": "IDFC FIRST Bank - customer care",
    "18602677777": "IndusInd Bank - customer care",
    "18001200": "Yes Bank - customer care",
}

app = Flask(__name__, static_folder="static")
# --- Defense API (SIH26104 screening) - try/except = server never breaks ---
try:
    from defense_api import bp as _defense_bp
    app.register_blueprint(_defense_bp)
    print("[OK] defense_api registered: /api/evidence/dossier, /api/npci/freeze, /api/challenge/verify")
except Exception as _e:
    print("[WARN] defense_api not loaded:", _e)

try:
    from flask_cors import CORS
    CORS(app)
    print("CORS: on")
except ImportError:
    print("CORS: flask-cors not installed - other devices may be blocked")

# ── TinyFish threat-verifier (parallel / non-blocking) ───────────────────────
try:
    from services.threat_verifier import verify_async, get_result as _tf_get
    _TINYFISH_HOOKED = True
    print("[OK] TinyFish threat-verifier loaded: background fraud-registry checks enabled")
except Exception as _tf_err:
    _TINYFISH_HOOKED = False
    print(f"[WARN] TinyFish threat-verifier not loaded: {_tf_err}")

# ── ElevenLabs Studio Service (ConvAI, Flash v2.5, Scribe STT) ────────────────
try:
    from services.elevenlabs_service import elevenlabs_svc
    _ELEVENLABS_HOOKED = True
    print("[OK] ElevenLabs Studio service loaded: ConvAI, Flash v2.5, Scribe STT enabled")
except Exception as _el_err:
    _ELEVENLABS_HOOKED = False
    print(f"[WARN] ElevenLabs Studio service not loaded: {_el_err}")

# ── ArmorIQ Intent Assurance Guard (Runtime Governance & Cryptographic Tokens) ──
try:
    from services.armoriq_guard import armoriq
    _ARMORIQ_HOOKED = True
    print("[OK] ArmorIQ Intent Assurance loaded: cryptographic circuit-breaker active")
except Exception as _aiq_err:
    _ARMORIQ_HOOKED = False
    print(f"[WARN] ArmorIQ Intent Assurance not loaded: {_aiq_err}")



def score_audio(y):
    piece = fix_length(np.asarray(y, dtype=np.float32), int(SECONDS * SR))
    x = logmel(piece)
    x = (x - x.mean()) / (x.std() + 1e-6)
    with torch.no_grad():
        p = float(torch.sigmoid(model(torch.from_numpy(x[None, None, ...]))))
    return p


def decode_to_wav(raw_bytes, suffix):
    tmp = tempfile.mkdtemp(prefix="dk_demo_")
    inp = os.path.join(tmp, "in" + suffix)
    out = os.path.join(tmp, "out.wav")
    with open(inp, "wb") as fh:
        fh.write(raw_bytes)
    run_quiet([FFMPEG, "-hide_banner", "-y", "-i", inp,
               "-ar", str(SR), "-ac", "1", out])
    return load(out)


def _serve_no_cache(filename):
    resp = make_response(send_file(filename))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

@app.route("/")
def index():
    target = "static/studio.html" if os.path.exists("static/studio.html") else "static/index.html"
    return _serve_no_cache(target)


@app.route("/studio")
def studio():
    return _serve_no_cache("static/studio.html")


@app.route("/telephony")
def telephony():
    return _serve_no_cache("static/index.html")


@app.route("/api/reset", methods=["POST"])
def reset():
    engine.reset()
    return jsonify({"ok": True})

@app.route("/api/ping", methods=["GET", "POST"])
def ping():
    return jsonify({"ok": True, "status": "ok", "online": True,
                    "backend": "online", "model": MODEL_NAME})

@app.route("/api/context", methods=["POST"])
def context():
    """What do we know about this number? TRAI numbering rules +
    local curated registry (live Sanchar Saathi API is the roadmap)."""
    d = request.get_json(force=True) if request.is_json else {}
    number = str(d.get("number", ""))
    for ch in "+-() ":
        number = number.replace(ch, "")
    if number.startswith("91") and len(number) == 12:
        number = number[2:]
    elif number.startswith("0") and len(number) == 11:
        number = number[1:]
    notes = []
    level = "neutral"
    if number.startswith("140"):
        notes.append("Number is in the TRAI 140 telemarketing series")
        level = "warning"
    if number in OFFICIAL_NUMBERS:
        notes.append(f"Matches official listing: {OFFICIAL_NUMBERS[number]}")
        level = "safe" if level == "neutral" else level
    elif len(number) == 10 and number[0] in "6789":
        notes.append("Mobile number - registries cannot verify individuals; "
                     "judge the call by what the caller says and asks for")
    elif number.startswith("1800") or number.startswith("1860"):
        notes.append("Toll-free number not in our local registry - if it claims "
                     "to be your bank, verify on the bank's official website")
    else:
        notes.append("Not in our local registry of official helplines")
    if d.get("claims_bank") and number not in OFFICIAL_NUMBERS:
        notes.append("Caller claims to be from a bank but the number is not the "
                     "bank's official helpline - classic impersonation pattern")
        level = "danger"
    return jsonify({"number": number, "level": level, "notes": notes})




@app.route("/api/enrol", methods=["POST"])
def enrol():
    try:
        name = "".join(c for c in request.form.get("name", "") if c.isalnum() or c in " _-").strip()
        if not name:
            return jsonify({"error": "name required"})
        f = request.files.get("audio")
        suffix = os.path.splitext(f.filename)[1] or ".wav"
        y = decode_to_wav(f.read(), suffix)
        voiceprint_falak.enrol(name, [y])
        return jsonify({"ok": True, "name": name,
                        "enrolled": voiceprint_falak.enrolled_names()})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/verify", methods=["POST"])
def verify():
    try:
        name = request.form.get("name", "").strip()
        f = request.files.get("audio")
        suffix = os.path.splitext(f.filename)[1] or ".wav"
        y = decode_to_wav(f.read(), suffix)
        return jsonify(voiceprint_falak.verify(name, y))
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/voiceprints", methods=["GET"])
def voiceprints():
    return jsonify({"enrolled": voiceprint_falak.enrolled_names()})


@app.route("/api/score", methods=["POST"])
def api_score():
    try:
        ctype = request.headers.get("Content-Type", "")
        if "webm" in ctype or "ogg" in ctype:
            suffix = ".webm"
        elif "wav" in ctype:
            suffix = ".wav"
        elif "mpeg" in ctype or "mp3" in ctype:
            suffix = ".mp3"
        elif "mp4" in ctype or "m4a" in ctype:
            suffix = ".m4a"
        else:
            suffix = ".bin"
        if "multipart/form-data" in ctype:
            f = next(iter(request.files.values()), None)
            raw_bytes = f.read() if f is not None else b""
            if f is not None and f.filename and "." in f.filename:
                suffix = "." + f.filename.rsplit(".", 1)[-1].lower()
        elif "json" in ctype:
            import base64 as _b64
            raw_bytes = b""
            try:
                d = request.get_json(force=True, silent=True) or {}
                s = d.get("audio") or d.get("data") or d.get("blob") or d.get("file") or ""
                if isinstance(s, str) and s:
                    raw_bytes = _b64.b64decode(s.split(",")[-1])
            except Exception:
                raw_bytes = b""
            if not raw_bytes:
                raw_bytes = request.get_data()
        else:
            raw_bytes = request.get_data()
        print(f"[score] in: ctype={ctype}, bytes={len(raw_bytes)}, suffix={suffix}")
        if not raw_bytes:
            return jsonify({"error": "no audio received"})
        y = decode_to_wav(raw_bytes, suffix)       
        if len(y) < SR:
            return jsonify({"error": "too short"})
        vfrac = float(energy_vad(y[-int(SECONDS * SR):]).mean())
        if vfrac < float(CAL.get("vad_min", 0.0)):
            r = engine.update(0.5, 0.0)
        else:
            raw = score_audio(y)
            bias = float(CAL.get("logit_bias", 0.0))
            q = min(max(raw, 1e-4), 1 - 1e-4)
            p = 1.0 / (1.0 + math.exp(-(math.log(q / (1.0 - q)) + bias)))
            r = engine.update(p, vfrac * SECONDS)
        pol = policy_for(r["tier"])

        # ── TinyFish parallel check (non-blocking) ────────────────────────────
        # Fire the web fraud-registry lookup in the background so it NEVER
        # delays the primary inference response.  The job_id is included in
        # the payload; the frontend may poll /api/tinyfish/result?job=<id>.
        tf_job_id = None
        if _TINYFISH_HOOKED and r.get("tier") in ("MEDIUM", "HIGH"):
            try:
                caller_num = (request.get_json(silent=True) or {}).get("caller_number", "")
                tf_job_id = verify_async(caller_number=str(caller_num))
            except Exception as _tf_ex:
                pass  # background check failing must never affect primary verdict
        # ─────────────────────────────────────────────────────────────────────

        resp = {
            "window_p": round(r["window_p"], 4),
            "call_p": round(r["call_p"], 4),
            "tier": r["tier"],
            "voiced_seconds": r["voiced_seconds"],
            "n_windows": r["n_windows"],
            "action": pol["action"],
            "ui": pol["ui"],
            "step_up": pol["step_up"],
            "allow_sensitive": pol["allow_sensitive_action"],
            "model": MODEL_NAME,
        }
        if tf_job_id:
            resp["tinyfish_job_id"] = tf_job_id
        return jsonify(resp)
    except Exception as e:
        return jsonify({"error": str(e)})


# ═════════════════════════════════════════════════════════════════════════════
# ── DHWANI KAVACH STUDIO :: ElevenLabs Backend Endpoints ──────────────────────
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/api/studio/permissions", methods=["GET"])
def studio_permissions():
    """Live diagnostics on ElevenLabs API key and capabilities."""
    if not _ELEVENLABS_HOOKED:
        return jsonify({"ok": False, "error": "ElevenLabs service not loaded"}), 503
    try:
        res = elevenlabs_svc.probe_permissions()
        res["ok"] = True
        return jsonify(res)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/studio/agent/create", methods=["POST"])
def studio_agent_create():
    """
    No-code ConvAI Agent creation endpoint.
    PPT Slide 3 & 4: User prompt -> ElevenLabs /v1/convai/agents/create.
    """
    if not _ELEVENLABS_HOOKED:
        return jsonify({"ok": False, "error": "ElevenLabs service not loaded"}), 503
    try:
        data = request.get_json(silent=True) or {}
        name = data.get("name", "Dhwani Kavach Assistant").strip()
        prompt = data.get("prompt", "You are a customer support agent.").strip()
        voice_id = data.get("voice_id")
        first_message = data.get("first_message")
        language = data.get("language", "en")
        model_id = data.get("model_id")

        if not prompt:
            return jsonify({"ok": False, "error": "Agent prompt cannot be empty"}), 400

        res = elevenlabs_svc.create_convai_agent(
            name=name,
            prompt=prompt,
            voice_id=voice_id,
            first_message=first_message,
            language=language,
            model_id=model_id
        )
        res["ok"] = res.get("success", False)
        return jsonify(res)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/studio/agent/signed_url", methods=["GET"])
def studio_agent_signed_url():
    """Returns signed WebSocket/WebRTC URL to converse with an agent."""
    if not _ELEVENLABS_HOOKED:
        return jsonify({"ok": False, "error": "ElevenLabs service not loaded"}), 503
    try:
        agent_id = request.args.get("agent_id", "").strip()
        if not agent_id:
            return jsonify({"ok": False, "error": "agent_id query parameter required"}), 400
        res = elevenlabs_svc.get_signed_conversation_url(agent_id=agent_id)
        res["ok"] = res.get("success", False)
        return jsonify(res)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/studio/intercept_alert", methods=["POST"])
def studio_intercept_alert():
    """
    Ultra-low latency security voice warning injection via Flash v2.5.
    PPT Slide 4, 5 & 7: Instant ElevenLabs voice warning + call termination.
    Governed by ArmorIQ Intent Assurance cryptographic circuit-breaker.
    """
    if not _ELEVENLABS_HOOKED:
        return jsonify({"ok": False, "error": "ElevenLabs service not loaded"}), 503
    try:
        data = request.get_json(silent=True) or {}
        text = data.get(
            "text",
            "Security Alert: Dhwani Kavach Shield has detected a synthetic voice clone and scam pattern. This call is placed on hold."
        )
        voice_id = data.get("voice_id")
        action = data.get("action", "VOICE_INTERCEPT_ALERT")
        risk_score = float(data.get("risk_score", 0.94))

        # ArmorIQ Intent Assurance Verification
        armoriq_intent_id = None
        armoriq_verification = None
        if _ARMORIQ_HOOKED:
            armoriq_verification = armoriq.verify_action_intent(
                action=action,
                risk_score=risk_score,
                context={"text": text, "voice_id": voice_id}
            )
            armoriq_intent_id = armoriq_verification.get("intent_id")
            if not armoriq_verification.get("authorized", False):
                return jsonify({
                    "ok": False,
                    "error": armoriq_verification.get("reason", "Action rejected by ArmorIQ policy"),
                    "armoriq_intent_id": armoriq_intent_id,
                    "armoriq_verification": armoriq_verification
                }), 403

        res = elevenlabs_svc.generate_flash_intercept_alert(text=text, voice_id=voice_id)
        res["ok"] = res.get("success", False)
        if armoriq_intent_id:
            res["armoriq_intent_id"] = armoriq_intent_id
        if armoriq_verification:
            res["armoriq_verification"] = armoriq_verification
        return jsonify(res)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/studio/armoriq/verify", methods=["POST"])
def studio_armoriq_verify():
    """Cryptographic action intent verification under ArmorIQ runtime policy."""
    if not _ARMORIQ_HOOKED:
        return jsonify({"ok": False, "error": "ArmorIQ guard service not loaded"}), 503
    try:
        data = request.get_json(silent=True) or {}
        action = data.get("action", "TERMINATE_CALL")
        risk_score = float(data.get("risk_score", 0.94))
        context = data.get("context", {})
        threshold = float(data.get("threshold", 0.75))
        receipt = armoriq.verify_action_intent(
            action=action,
            risk_score=risk_score,
            context=context,
            threshold=threshold
        )
        return jsonify({
            "ok": True,
            "authorized": receipt.get("authorized", False),
            "armoriq_intent_id": receipt.get("intent_id"),
            "armoriq_verification": receipt
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    import socket
    try:
        _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _s.connect(("8.8.8.8", 80))
        _lan_ip = _s.getsockname()[0]
        _s.close()
    except Exception:
        _lan_ip = "(run ipconfig to find it)"
    print()
    print("DHWANI-KAVACH demo v2. Open in your browser (Chrome recommended):")
    print("       http://127.0.0.1:8000")
    print(f"phones on the same Wi-Fi:  http://{_lan_ip}:8000")
    try:
        import uvicorn
        print("[OK] Launching ASGI Uvicorn server for native WebSockets & Edge NPU stream.")
        uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
    except Exception as _uv_err:
        print(f"[WARN] Uvicorn fallback to WSGI: {_uv_err}")
        app.run(host="0.0.0.0", port=8000, debug=False)
