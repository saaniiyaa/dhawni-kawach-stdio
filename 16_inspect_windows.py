# 16_inspect_windows.py
# The calibration found 6 "suspicious" windows INSIDE your real recording.
# This tool cuts those exact moments out into small wav files so you can
# LISTEN to them and tell me what they are (breath? rustle? quiet speech?).
# Ears are the debugging tool tonight. Run time: ~20 seconds.

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import glob

import numpy as np
import soundfile as sf
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

NEED, HOP, VAD_MIN, HIGH = 4.0, 2.0, 0.25, 0.5
os.makedirs(os.path.join("results", "inspect"), exist_ok=True)

for f in sorted(glob.glob("data/team/*.wav")):
    name = os.path.splitext(os.path.basename(f))[0]
    y = load(f)
    need, hop = int(NEED * SR), int(HOP * SR)
    print(f"\n{name}.wav  ({len(y)/SR:.0f}s)")
    exported = 0
    for start in range(0, max(len(y) - need + 1, 1), hop):
        w = y[start:start + need]
        if len(w) < need:
            w = np.pad(w, (0, need - len(w)))
        vfrac = float(energy_vad(w).mean())
        if vfrac < VAD_MIN:
            continue                      # pauses are already understood
        x = logmel(w)
        x = (x - x.mean()) / (x.std() + 1e-6)
        with torch.no_grad():
            s = float(torch.sigmoid(model(torch.from_numpy(x[None, None, ...]))))
        flag = ""
        if s >= HIGH:
            peak = float(np.abs(w).max()) + 1e-9
            audible = (w / peak * 0.9).astype("float32")   # make quiet bits listenable
            fn = f"{name}__at_{start//SR:02d}s__score_{s:.2f}.wav"
            sf.write(os.path.join("results", "inspect", fn), audible, SR)
            exported += 1
            flag = "  <- EXPORTED, listen to this"
        print(f"   t={start//SR:02d}s  speech={vfrac*100:3.0f}%  score={s:.2f}{flag}")
    if exported == 0:
        print("   (no suspicious windows in this file)")

print()
print("DONE. Open the folder  results/inspect  and double-click each wav.")
print("Listen and tell the mentor WHAT THEY ARE: breath / rustle / fan /")
print("very quiet speech / normal speech / something else. That answer")
print("decides the next fix.")