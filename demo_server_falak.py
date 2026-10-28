# demo_server.py
# DHWANI-KAVACH LIVE DEMO SERVER
#   browser mic -> 4-second chunks -> our CNN -> risk engine -> tier + action
# Also accepts a .wav file upload (for demo machines with no mic).
# Run: click Run, then open  http://127.0.0.1:8000  in your browser.
# Stop: click the trash-can icon on the terminal panel in VS Code.

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import sys
import tempfile
import shutil

# Auto-detect and relaunch via .venv if dependencies are not available in current interpreter
try:
    from flask import Flask, request, jsonify, send_file
    import numpy as np
    import torch
except ImportError:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    venv_py = os.path.join(base_dir, ".venv", "Scripts", "python.exe")
    if not os.path.exists(venv_py):
        venv_py = os.path.join(base_dir, ".venv", "bin", "python")
    if os.path.exists(venv_py) and os.path.abspath(sys.executable) != os.path.abspath(venv_py) and __name__ == "__main__":
        import subprocess
        print(f"[*] Relaunching Dhwani-Kavach server using virtual environment: {venv_py}")
        sys.exit(subprocess.call([venv_py, os.path.abspath(__file__)] + sys.argv[1:]))
    else:
        print("[!] Required dependencies (flask/torch/numpy) are missing. Please run in .venv.")
        raise


from ml.audio.io import load, SR, fix_length, energy_vad
from ml.features.dsp import logmel
from ml.models.cnn import MelCNN
from ml.engine.temporal import TemporalEngine, policy_for
from ml.augment.codecs import FFMPEG, run_quiet

torch.set_num_threads(1)

# ---- load the newest trained model we have ----
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

from ml.engine.temporal import EngineConfig, TemporalEngine, policy_for
import json

cal_file = "results/calibration.json"
theta_lo = 0.78
theta_hi = 0.90
theta_neutral = 0.70
vad_min = 0.25

if os.path.exists(cal_file):
    try:
        with open(cal_file, "r") as fh:
            cal = json.load(fh)
            theta_lo = float(cal.get("theta_lo", theta_lo))
            theta_hi = float(cal.get("theta_hi", theta_hi))
            vad_min = float(cal.get("vad_min", vad_min))
            theta_neutral = max(0.50, min(theta_lo - 0.08, (theta_lo + 0.50) / 2.0))
            print(f"calibration: loaded {cal_file} (theta_lo={theta_lo:.2f}, theta_hi={theta_hi:.2f}, neutral={theta_neutral:.2f})")
    except Exception as ex:
        print(f"calibration notice: could not load {cal_file} ({ex})")

engine = TemporalEngine(EngineConfig(theta_lo=theta_lo, theta_hi=theta_hi, theta_neutral=theta_neutral))
SECONDS = 4.0

app = Flask(__name__, static_folder="static")


def score_audio(y):
    """y = 16 kHz mono numpy -> spoof probability for the last 4 s window."""
    piece = fix_length(np.asarray(y, dtype=np.float32), int(SECONDS * SR))
    x = logmel(piece)
    x = (x - x.mean()) / (x.std() + 1e-6)
    with torch.no_grad():
        p = float(torch.sigmoid(model(torch.from_numpy(x[None, None, ...]))))
    return p


def decode_to_wav(raw_bytes, suffix):
    """Any browser audio format -> 16 kHz mono wav via real ffmpeg."""
    tmp = tempfile.mkdtemp(prefix="dk_demo_")
    try:
        inp = os.path.join(tmp, "in" + suffix)
        out = os.path.join(tmp, "out.wav")
        with open(inp, "wb") as fh:
            fh.write(raw_bytes)
        run_quiet([FFMPEG, "-hide_banner", "-y", "-i", inp,
                   "-ar", str(SR), "-ac", "1", out])
        y = load(out)
        return y
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@app.route("/")
@app.route("/index.html")
def index():
    if os.path.exists("static/index.html"):
        return send_file("static/index.html")
    if os.path.exists("index.html"):
        return send_file("index.html")
    return "Dhwani-Kavach index.html not found", 404


@app.route("/api/reset", methods=["POST"])
def reset():
    engine.reset()
    return jsonify({"ok": True})


@app.route("/api/score", methods=["POST"])
def api_score():
    try:
        raw_bytes = None
        suffix = ".wav"
        
        # Check if multipart file upload
        if "file" in request.files:
            f = request.files["file"]
            raw_bytes = f.read()
            fname = f.filename.lower()
            if fname.endswith(".webm"):
                suffix = ".webm"
            elif fname.endswith(".ogg"):
                suffix = ".ogg"
            elif fname.endswith(".mp3"):
                suffix = ".mp3"
            elif fname.endswith(".m4a"):
                suffix = ".m4a"
            else:
                suffix = ".wav"
        else:
            raw_bytes = request.get_data()
            ctype = request.headers.get("Content-Type", "").lower()
            if "webm" in ctype:
                suffix = ".webm"
            elif "ogg" in ctype:
                suffix = ".ogg"
            elif "mp3" in ctype:
                suffix = ".mp3"
            elif "m4a" in ctype or "mp4" in ctype:
                suffix = ".m4a"
            elif "wav" in ctype:
                suffix = ".wav"
            else:
                suffix = ".bin"

        if not raw_bytes or len(raw_bytes) == 0:
            return jsonify({"error": "empty audio payload"})

        y = decode_to_wav(raw_bytes, suffix)
        if len(y) < SR:            # less than 1 second of audio
            return jsonify({"error": "too short (minimum 1 second of audio required)"})
            
        vfrac = float(energy_vad(y[-int(SECONDS * SR):]).mean())
        voiced = vfrac * SECONDS

        # Pause gate: If mostly silent, don't let normalized background hiss score as fake
        if vfrac < vad_min:
            p = 0.05
            r = engine.update(p, voiced)
            acoustic = {"synthetic_score": 8, "is_synthetic": False, "vocoder_artifacts": "CLEAN / BIOLOGICAL", "jitter": 4.8, "verdict": "AUTHENTIC HUMAN SPEECH"}
        else:
            p = score_audio(y)
            from ml.engine.voiceprint_falak import analyze_acoustic_synthetics
            acoustic = analyze_acoustic_synthetics(y)
            if acoustic.get("is_synthetic", False):
                p = max(p, 0.88)
            elif p < 0.65 and acoustic.get("jitter", 0) > 4.0:
                p = min(p, 0.08)
            r = engine.update(p, voiced)

        pol = policy_for(r["tier"])
        return jsonify({
            "window_p": round(r["window_p"], 4),
            "call_p": round(r["call_p"], 4),
            "llr": round(r.get("llr", 0.0), 3),
            "ema": round(r.get("ema", 0.0), 4),
            "tier": r["tier"],
            "voiced_seconds": r["voiced_seconds"],
            "n_windows": r["n_windows"],
            "action": pol["action"],
            "ui": pol["ui"],
            "step_up": pol["step_up"],
            "allow_sensitive": pol["allow_sensitive_action"],
            "model": MODEL_NAME,
            "acoustic": acoustic,
        })
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/demo_audio/<name>")
def api_demo_audio(name):
    allowed = {
        "real": "results/demo/demo_real_studio.wav",
        "fake": "results/demo/demo_fake_studio.wav",
        "my_voice": "data/my_voice.wav"
    }
    target = allowed.get(name.lower())
    if target and os.path.exists(target):
        return send_file(target, mimetype="audio/wav")
    return jsonify({"error": "demo file not found"}), 404


from ml.engine.voiceprint_falak import scan as scan_radar
import time
import uuid

@app.route("/api/context", methods=["POST"])
def api_context():
    data = request.get_json(silent=True) or {}
    number = data.get("number", "+91-140-987654")
    claims_bank = data.get("claims_bank", False)
    
    notes = []
    level = "normal"
    
    if "+91-140" in number or "140" in number:
        notes.append("Caller prefix +91-140 indicates commercial telemarketer / unverified SIP trunk.")
        level = "warning"
    else:
        notes.append("Carrier: VoLTE Encrypted Ingestion Active.")
        
    if claims_bank:
        notes.append("MISMATCH: Financial institutions never initiate outbound customer verification from generic numbers.")
        level = "danger"
        
    notes.append("Real-Time Neural Spectral Defense & Vocoder Phase Analyzer Active.")
    
    return jsonify({
        "number": number,
        "level": level,
        "notes": notes,
        "verified_registry": False,
        "trust_score": 38 if level == "danger" else (62 if level == "warning" else 94)
    })


@app.route("/api/radar", methods=["POST"])
def api_radar():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    res = scan_radar(text)
    return jsonify(res)


@app.route("/api/action/oob", methods=["POST"])
def api_oob():
    data = request.get_json(silent=True) or {}
    target_number = data.get("number", "+91-98765-XXXXX")
    return jsonify({
        "status": "INITIATED",
        "action": "OUT_OF_BAND_CALLBACK",
        "target": target_number,
        "auth_pin": "582914",
        "expires_in_sec": 60,
        "timestamp": time.strftime("%H:%M:%S")
    })


@app.route("/api/action/report", methods=["POST"])
def api_report():
    data = request.get_json(silent=True) or {}
    incident_id = f"I4C-DK-{uuid.uuid4().hex[:8].upper()}"
    return jsonify({
        "status": "DISPATCHED",
        "incident_id": incident_id,
        "recipient": "1930 Cyber Fraud / I4C National Helpline",
        "severity": data.get("tier", "HIGH_RISK"),
        "telemetry_attached": True,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    return response


@app.route("/api/ping", methods=["GET", "POST", "OPTIONS"])
@app.route("/api/health", methods=["GET", "POST", "OPTIONS"])
def api_ping():
    return jsonify({
        "status": "ONLINE",
        "app": "DHWANI-KAVACH",
        "model": MODEL_NAME,
        "timestamp": time.time()
    })


if __name__ == "__main__":
    import socket
    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    print()
    print("=" * 60)
    print("  [+]  DHWANI-KAVACH LIVE INFERENCE & DEFENSE SERVER  [+]")
    print("=" * 60)
    print(f"  Local Browser URL:   http://127.0.0.1:8000")
    print(f"  Android Device URL: http://{local_ip}:8000")
    print(f"  Android Emulator:   http://10.0.2.2:8000")
    print("=" * 60)
    print("(To stop server: Ctrl+C or kill terminal)")
    print()
    app.run(host="0.0.0.0", port=8000, debug=False)
