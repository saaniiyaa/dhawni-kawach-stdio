# 13_make_benchmark_pair.py  (v2 - uses the project's own dataset loader)
# v1 lesson: the eval protocol file has extra columns on some copies; our
# loader is format-tolerant, v1's hand-made parser was not (0 real, 0 spoof).
# v2 uses ml.datasets.asvspoof19.parse_protocol - the SAME code that trained
# the model - so it cannot disagree with the dataset.
# It picks + verifies the two voice-note demo files:
#   results/demo/demo_real_studio.wav  -> REAL voice   (should score SAFE)
#   results/demo/demo_fake_studio.wav  -> CLONE/SPOOF  (should score HIGH)
# Ends with PAIR OK (demo-safe) or PAIR WEAK (paste output to mentor).
# Run time: ~2-4 minutes.

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import random

import numpy as np
import soundfile as sf
import torch

from ml.audio.io import load, SR, fix_length
from ml.datasets.asvspoof19 import parse_protocol, LA_ROOT
from ml.features.dsp import logmel
from ml.models.cnn import MelCNN

torch.set_num_threads(2)
random.seed(0)

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


def cnn_score(y):
    """Avg CNN score over 4 s windows (0=real, 1=fake)."""
    need = 4 * SR
    y = fix_length(y, need)
    vals = []
    for start in range(0, len(y) - need + 1, 2 * SR):
        x = logmel(y[start:start + need])
        x = (x - x.mean()) / (x.std() + 1e-6)
        with torch.no_grad():
            p = float(torch.sigmoid(model(torch.from_numpy(x[None, None, ...]))))
        vals.append(p)
    return float(np.mean(vals))


rows = parse_protocol(LA_ROOT, "eval")
bonafide = [r["path"] for r in rows if r["label"] == "bonafide"]
spoofs = [(r["attack"], r["path"]) for r in rows if r["label"] == "spoof"]
print(f"dataset root: {LA_ROOT}")
print(f"candidates from loader: {len(bonafide)} real, {len(spoofs)} spoof\n")
if not bonafide or not spoofs:
    print("Loader found no eval rows - paste this to the mentor.")
    raise SystemExit(0)

random.shuffle(bonafide)
by_attack = {}
for att, path in spoofs:
    by_attack.setdefault(att, []).append(path)
for att in by_attack:
    random.shuffle(by_attack[att])
spoof_pick = [(att, paths[0]) for att, paths in sorted(by_attack.items())]

best_real, best_real_s = None, 9.9
best_fake, best_fake_s, best_fake_att = None, -1.0, ""
print("scoring candidates (real)...")
for path in bonafide[:8]:
    if not os.path.exists(path):
        continue
    s = cnn_score(load(path))
    print(f"  real  {os.path.basename(path)}  score {s:.2f}")
    if s < best_real_s:
        best_real, best_real_s = path, s
print("scoring candidates (spoof, one per attack type)...")
for att, path in spoof_pick:
    if not os.path.exists(path):
        continue
    s = cnn_score(load(path))
    print(f"  spoof {os.path.basename(path)} [{att}]  score {s:.2f}")
    if s > best_fake_s:
        best_fake, best_fake_s, best_fake_att = path, s, att

if best_real is None or best_fake is None:
    print("Could not find usable files. Tell the mentor what printed above.")
    raise SystemExit(0)

os.makedirs("results/demo", exist_ok=True)
out = {}
for role, path in [("demo_real_studio", best_real), ("demo_fake_studio", best_fake)]:
    y = load(path)
    y = y[:10 * SR]
    dst = os.path.join("results", "demo", role + ".wav")
    sf.write(dst, y, SR)
    out[role] = dst

print()
print("FINAL CHECK (scoring the actual wav files):")
s_real = cnn_score(load(out["demo_real_studio"]))
s_fake = cnn_score(load(out["demo_fake_studio"]))
print(f"  demo_real_studio.wav  [{os.path.basename(best_real)}]  score {s_real:.2f}  (want LOW)")
print(f"  demo_fake_studio.wav  [{os.path.basename(best_fake)}, attack {best_fake_att}]  score {s_fake:.2f}  (want HIGH)")
if s_real < 0.5 and s_fake > 0.8:
    print("\nPAIR OK - demo-safe. Use these in the voice-note scene:")
else:
    print("\nPAIR WEAK - paste this output to the mentor before the demo.")
for p in out.values():
    print("  ", p)
print()
print("Voice-note scene: Choose File -> demo_real_studio.wav = SAFE advisory;")
print("                 Choose File -> demo_fake_studio.wav = HIGH RISK + hold.")
print("Say honestly: these are benchmark samples - the model's home domain.")