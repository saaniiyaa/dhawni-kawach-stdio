# 12_check_my_voice.py
# DIAGNOSTIC: what score does the model ACTUALLY give YOUR real voice?
# No engine, no tiers - just the raw truth, same CNN the demo uses.

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import glob

import numpy as np
import torch

from ml.audio.io import load, SR, fix_length
from ml.augment.codecs import apply_codec
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
print("model:", MODEL_NAME)
print()

files = sorted(glob.glob("data/team/*.wav")) + sorted(glob.glob("data/*.wav"))
if not files:
    print("No voice files (need data/my_voice.wav or data/team/*.wav).")
    raise SystemExit(0)


def window_scores(y):
    """Raw CNN score for each 4 s window of a clip (0=real, 1=fake)."""
    out = []
    step = 2 * SR                       # 4 s window, 2 s hop
    need = 4 * SR
    y = fix_length(y, need * 2)
    for start in range(0, len(y) - need + 1, step):
        x = logmel(y[start:start + need])
        x = (x - x.mean()) / (x.std() + 1e-6)
        with torch.no_grad():
            p = float(torch.sigmoid(model(torch.from_numpy(x[None, None, ...]))))
        out.append(p)
    return out


for f in files[:6]:
    name = os.path.basename(f)
    y = load(f)
    conds = [("original", y)]
    try:
        y_mu, _ = apply_codec(y, SR, "mulaw", workdir="data/cache", tag="diag")
        conds.append(("after phone codec", y_mu))
    except Exception:
        pass
    for label, audio in conds:
        s = window_scores(audio)
        tag = "REAL-voice OK" if np.mean(s) < 0.5 else (
              "calibratable" if np.mean(s) < 0.75 else "DOMAIN SHIFT - model unreliable here")
        print(f"{name:22s} {label:20s} avg {np.mean(s):.2f}  max {np.max(s):.2f}  -> {tag}")

print()
print("HOW TO READ THIS")
print(" avg < 0.50 : model is fine on your voice - the alarm was THRESHOLDS")
print(" avg 0.5-0.75: calibratable - Block 10 (threshold calibration) fixes it")
print(" avg > 0.75 : strong domain shift (mic+Indian speech vs English benchmark)")
print("              - tonight use FILE-based demo scenes + radar/voiceprint,")
print("                and Block 10 becomes the top priority")
print()
print("Paste this output to the mentor.")