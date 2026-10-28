# 14_block10_calibrate.py  (Block 10: calibrate the warning line on REAL voices)
# It plays YOUR recordings through the exact live pipeline (4-second windows),
# separates PAUSES from SPEECH, and writes results/calibration.json.
# The demo server then (a) stops scoring silent windows, (b) re-centres the
# warning line on YOUR real voice. Run time: about 1 minute.

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import glob
import json
import math
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
    print("No trained model found. Run 7_train_cnn.py first.")
    raise SystemExit(0)

model = MelCNN()
model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu"))
model.eval()

VAD_MIN = 0.25          # a window needs >= 25% speech energy to be judged
NEED = 4.0              # window length (seconds), same as the live demo
HOP = 2.0


def score_window(y):
    x = logmel(y)
    x = (x - x.mean()) / (x.std() + 1e-6)
    with torch.no_grad():
        return float(torch.sigmoid(model(torch.from_numpy(x[None, None, ...]))))


def logit(p):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def sigmoid(z):
    return 1.0 / (1.0 + math.exp(-z))


def all_windows(path):
    y = load(path)
    need, hop = int(NEED * SR), int(HOP * SR)
    out = []
    for start in range(0, max(len(y) - need + 1, 1), hop):
        w = y[start:start + need]
        if len(w) < need:
            w = np.pad(w, (0, need - len(w)))
        out.append(w)
    return out


files = sorted(glob.glob("data/team/*.wav"))
if not files:
    print("No recordings found in data/team/. Run 5_record_team.py first.")
    raise SystemExit(0)

silent_scores, voiced_scores = [], []
print(f"model: {MODEL_NAME}   recordings: {[os.path.basename(f) for f in files]}")
print(f"slicing each clip into {NEED:.0f}s windows and separating PAUSE vs SPEECH...\n")

for f in files:
    for w in all_windows(f):
        vfrac = float(energy_vad(w).mean())
        s = score_window(w)
        (voiced_scores if vfrac >= VAD_MIN else silent_scores).append(s)

ns, nv = len(silent_scores), len(voiced_scores)
print(f"WINDOWS: {ns} mostly-silent (pauses), {nv} speech windows\n")

if ns:
    print(f"PAUSE windows:  avg {np.mean(silent_scores):.2f}  max {np.max(silent_scores):.2f}"
          f"   <- these were poisoning the call (model scores silence ~fake)")
if nv:
    v = np.array(voiced_scores)
    print(f"SPEECH windows: avg {v.mean():.2f}  p95 {np.percentile(v, 95):.2f}  max {v.max():.2f}")

fake_path = os.path.join("results", "demo", "demo_fake_studio.wav")
if os.path.exists(fake_path):
    fs = [score_window(w) for w in all_windows(fake_path)]
    print(f"KNOWN-FAKE file: avg {np.mean(fs):.2f}  (benchmark sample, should be high)")
print()

cal = {"vad_min": VAD_MIN, "date": str(date.today()),
       "model": MODEL_NAME, "n_silent": ns, "n_voiced": nv,
       "source": [os.path.basename(f) for f in files]}

if nv >= 8:
    mean_logit_v = float(np.mean([logit(s) for s in voiced_scores]))
    bias = logit(0.35) - mean_logit_v          # re-centre real speech at 0.35
    eff = [sigmoid(logit(s) + bias) for s in voiced_scores]
    fake_ok = True
    if os.path.exists(fake_path):
        f_eff = [sigmoid(logit(s) + bias) for s in fs]
        fake_ok = float(np.mean(f_eff)) >= 0.80
    cal.update({"logit_bias": round(bias, 3) if fake_ok else 0.0,
                "theta_lo": 0.62 if fake_ok else 0.5,
                "theta_hi": 0.90 if fake_ok else 0.8,
                "real_voiced_mean_raw": round(float(np.mean(voiced_scores)), 3),
                "real_voiced_mean_calibrated": round(float(np.mean(eff)), 3)})
    verdict = ("CALIBRATION OK - silent windows now skipped, real speech re-centred."
               if fake_ok else
               "CALIBRATION WEAK - bias would push fakes too low; wrote silence-gate only. Keep mic scene OFF.")
else:
    cal.update({"logit_bias": 0.0, "theta_lo": 0.5, "theta_hi": 0.8})
    verdict = ("NOT ENOUGH SPEECH WINDOWS - record more (60 s each, 5_record_team.py),"
               " then re-run. Mic scene stays OFF until then.")

os.makedirs("results", exist_ok=True)
with open(os.path.join("results", "calibration.json"), "w") as fh:
    json.dump(cal, fh, indent=2)

print("VERDICT:", verdict)
print("Saved: results/calibration.json")
print()
print("PASTE THIS TO THE MENTOR:")
print(json.dumps(cal, indent=2))