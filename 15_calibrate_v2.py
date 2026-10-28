# 15_calibrate_v2.py  (Block 10 v2 - two-sided calibration)
# v1 lesson: our data has TWO hills (real voice ~0.1, AI voice ~1.0), and
# averaging two hills puts the line in the wrong place. v2 uses LABELS:
#   FAKE side = files whose name starts with ai/fake/clone/tts/spoof
#               (or contains _ai/_fake/_clone/_tts/_spoof)
#   REAL side = every other file in data/team/
# The warning line goes in the GAP between the two sides. Scores are NOT
# shifted (bias stays 0) - the line moves, not the voices.
# Writes results/calibration.json (same file the server already reads).
# Then: restart the server. No code edits needed.

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import glob
import json
from datetime import date

import numpy as np
import torch

from ml.audio.io import load, SR, energy_vad
from ml.features.dsp import logmel
from ml.models.cnn import MelCNN

torch.set_num_threads(2)

MODEL_PATH, MODEL_NAME = None, None
for cand, name in [("results/cnn_v2/model.pt", "CNN v2"),
                   ("results/cnn_v1/model.pt", "CNN v1")]:
    if os.path.exists(cand):
        MODEL_PATH, MODEL_NAME = cand, name
        break
if MODEL_PATH is None:
    print("No trained model found."); raise SystemExit(0)

model = MelCNN()
model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu"))
model.eval()

VAD_MIN = 0.25
NEED, HOP = 4.0, 2.0
FAKE_START = ("ai", "fake", "clone", "tts", "spoof")
FAKE_CONTAINS = ("_ai", "_fake", "_clone", "_tts", "_spoof")


def score_window(y):
    x = logmel(y)
    x = (x - x.mean()) / (x.std() + 1e-6)
    with torch.no_grad():
        return float(torch.sigmoid(model(torch.from_numpy(x[None, None, ...]))))


def speech_windows(path):
    """All mostly-speech 4 s windows of a clip, with their scores."""
    y = load(path)
    need, hop = int(NEED * SR), int(HOP * SR)
    out = []
    for start in range(0, max(len(y) - need + 1, 1), hop):
        w = y[start:start + need]
        if len(w) < need:
            w = np.pad(w, (0, need - len(w)))
        if float(energy_vad(w).mean()) >= VAD_MIN:
            out.append(score_window(w))
    return out


files = sorted(glob.glob("data/team/*.wav"))
if not files:
    print("No recordings in data/team/. Run 5_record_team.py first."); raise SystemExit(0)

real_files = [f for f in files if not (
    os.path.splitext(os.path.basename(f))[0].lower().startswith(FAKE_START)
    or any(k in os.path.splitext(os.path.basename(f))[0].lower() for k in FAKE_CONTAINS))]
fake_files = [f for f in files if f not in real_files]

print(f"model: {MODEL_NAME}")
print(f"REAL side: {[os.path.basename(f) for f in real_files]}")
print(f"FAKE side: {[os.path.basename(f) for f in fake_files]}")
print()


def hist(label, scores):
    print(f"{label}: n={len(scores)}  avg {np.mean(scores):.2f}  "
          f"min {np.min(scores):.2f}  max {np.max(scores):.2f}")
    buckets = np.histogram(scores, bins=10, range=(0, 1))[0]
    for i, c in enumerate(buckets):
        if c:
            print(f"   {i/10:.1f}-{(i+1)/10:.1f}  {'#' * int(c)}")
    print()


real_scores = [s for f in real_files for s in speech_windows(f)]
fake_scores = [s for f in fake_files for s in speech_windows(f)]

if real_scores:
    hist("REAL windows", real_scores)
if fake_scores:
    hist("FAKE windows", fake_scores)

cal = {"vad_min": VAD_MIN, "date": str(date.today()), "model": MODEL_NAME,
       "logit_bias": 0.0,
       "real_files": [os.path.basename(f) for f in real_files],
       "fake_files": [os.path.basename(f) for f in fake_files]}

if len(real_scores) < 8:
    cal.update({"theta_lo": 0.62, "theta_hi": 0.90})
    verdict = ("NOT ENOUGH REAL SPEECH (need 8+ windows). Record 60 s more real voice "
               "(5_record_team.py), then re-run. Defaults written.")
elif not fake_files:
    cal.update({"theta_lo": 0.62, "theta_hi": 0.90})
    verdict = ("REAL SIDE ONLY - no ai/fake/clone/tts file found. Conservative defaults "
               "written. To enable the two-sided line, record the AI voice the same way "
               "and name the file ai.wav.")
else:
    r = np.array(real_scores); f = np.array(fake_scores)
    r_p95 = float(np.percentile(r, 95))       # top of the real hill
    f_p5 = float(np.percentile(f, 5))         # bottom of the fake hill
    cal["real_p95"] = round(r_p95, 3)
    cal["fake_p5"] = round(f_p5, 3)
    if f_p5 <= r_p95:
        cal.update({"theta_lo": 0.85, "theta_hi": 0.95})
        verdict = (f"SIDES OVERLAP (real p95 {r_p95:.2f} >= fake p5 {f_p5:.2f}) - "
                   "mic CNN scene stays OFF; use file-based scenes. "
                   "Very strict line written so real voices stay calm.")
    else:
        t_mid = (r_p95 + f_p5) / 2.0
        theta_hi = min(0.95, max(0.55, t_mid))
        theta_lo = min(theta_hi - 0.08, max(0.50, r_p95 + 0.35 * (t_mid - r_p95)))
        cal.update({"theta_lo": round(theta_lo, 3), "theta_hi": round(theta_hi, 3)})
        fa_est = float(np.mean(r > theta_hi))          # real windows above the red line
        miss_est = float(np.mean(f < theta_lo))        # fake windows below the warn line
        cal["fa_rate_on_our_data"] = round(fa_est, 3)
        cal["miss_rate_on_our_data"] = round(miss_est, 3)
        verdict = (f"TWO-SIDED LINE SET in the gap: real p95 {r_p95:.2f} | line "
                   f"{theta_lo:.2f}-{theta_hi:.2f} | fake p5 {f_p5:.2f}. "
                   f"On our own data: false-alarm {fa_est*100:.0f}%, miss {miss_est*100:.0f}%.")

os.makedirs("results", exist_ok=True)
with open(os.path.join("results", "calibration.json"), "w") as fh:
    json.dump(cal, fh, indent=2)

print("VERDICT:", verdict)
print("Saved: results/calibration.json")
print("NEXT: stop the server (trash-can), start it again, look for the line")
print("      'calibration: loaded ...' in its window, then F5 the browser.")
print()
print("PASTE THIS TO THE MENTOR:")
print(json.dumps(cal, indent=2))