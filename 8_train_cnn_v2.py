# 8_train_cnn_v2.py
# BLOCK 8 - THE KEY EXPERIMENT: does codec augmentation harden the detector?
#   v1 = model trained on clean audio (Block 7)
#   v2 = same model trained on audio pre-mangled by real phone/WhatsApp codecs
# We test BOTH models on: clean / landline (mulaw) / WhatsApp (opus16) audio.
# Whatever the table says - we report it honestly. That is the project's core claim.

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import csv
import json
import random
import time

import numpy as np

MANIFEST = os.path.join("data", "processed", "asvspoof19la", "manifest.csv")
CACHE    = os.path.join("data", "cache", "cnn_v2_aug")
TMP      = os.path.join("data", "cache", "codec_tmp")
OUT_DIR  = os.path.join("results", "cnn_v2")
V1_MODEL = os.path.join("results", "cnn_v1", "model.pt")

SECONDS = 4.0
MAX_REAL_TR, MAX_FAKE_TR = 2000, 2000
MAX_DEV, MAX_EVAL        = 800, 1200
EPOCHS, BATCH, LR        = 10, 16, 1e-3
SEED = 1234
AUG_P = 0.5                                   # fraction of train clips codec-mangled
CODEC_CHOICES = ["mulaw", "alaw", "amrnb", "opus16", "mp3_64"]

random.seed(SEED)
np.random.seed(SEED)

if not os.path.exists(MANIFEST):
    print("Manifest not found. Run 6_build_manifest.py first.")
    raise SystemExit(0)

import torch
import torch.nn as nn
from sklearn.metrics import roc_curve

from ml.audio.io import load, SR, fix_length
from ml.augment.codecs import apply_codec
from ml.features.dsp import logmel
from ml.models.cnn import MelCNN, count_params

torch.manual_seed(SEED)
torch.set_num_threads(2)
N_FRAMES = logmel(np.zeros(int(SECONDS * SR), dtype=np.float32)).shape[1]

rows = list(csv.DictReader(open(MANIFEST, encoding="utf-8")))
print("manifest rows:", len(rows))

def sample_split(split, max_real, max_fake):
    real = [r for r in rows if r["split"] == split and r["label"] == "bonafide"]
    fake = [r for r in rows if r["split"] == split and r["label"] == "spoof"]
    random.shuffle(real); random.shuffle(fake)
    return real[:max_real] + fake[:max_fake]

train_rows = sample_split("train", MAX_REAL_TR, MAX_FAKE_TR)
dev_rows   = sample_split("dev",   MAX_DEV // 2, MAX_DEV // 2)
eval_rows  = sample_split("eval",  MAX_EVAL // 2, MAX_EVAL // 2)
print(f"using: train {len(train_rows)} | dev {len(dev_rows)} | eval {len(eval_rows)}")


def build_cache(split_rows, tag, mode):
    """mode: 'clean' | 'aug' (random codec on train) | 'mulaw' | 'opus16'."""
    name = f"{tag}_{mode}"
    x_path = os.path.join(CACHE, f"X_{name}.npy")
    y_path = os.path.join(CACHE, f"y_{name}.npy")
    if os.path.exists(x_path) and os.path.exists(y_path):
        print(f"cache found: {name} - reusing")
        X = np.load(x_path, mmap_mode="r")
        return X, np.load(y_path)
    if os.path.exists(x_path):
        print(f"partial cache found for {name} (an earlier run was interrupted)")
        print("deleting it and rebuilding - do not worry, this is safe")
        os.remove(x_path)

    os.makedirs(CACHE, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    N = len(split_rows)
    X = np.lib.format.open_memmap(x_path, mode="w+", dtype=np.float16,
                                  shape=(N, 80, N_FRAMES))
    ys = []
    t0 = time.time()
    n_aug = 0
    for i, r in enumerate(split_rows):
        aud = fix_length(load(r["path"]), int(SECONDS * SR))
        if mode == "aug":
            if random.random() < AUG_P:
                codec = random.choice(CODEC_CHOICES)
                aud, _ = apply_codec(aud, SR, codec, workdir=TMP, tag="w")
                aud = fix_length(aud, int(SECONDS * SR))
                n_aug += 1
        elif mode in ("mulaw", "opus16"):
            aud, _ = apply_codec(aud, SR, mode, workdir=TMP, tag="w")
            aud = fix_length(aud, int(SECONDS * SR))
        X[i] = logmel(aud).astype(np.float16)
        ys.append(1 if r["label"] == "spoof" else 0)
        if (i + 1) % 100 == 0:
            speed = (i + 1) / max(time.time() - t0, 0.01)
            print(f"  {name}: {i+1}/{N}  ({speed:.1f}/s, ~{(N-i-1)/speed/60:.1f} min left)")
    if mode == "aug":
        print(f"  {name}: {n_aug}/{N} clips were codec-augmented")
    X.flush()
    ys = np.array(ys)
    np.save(os.path.join(CACHE, f"y_{name}.npy"), ys)
    return X, ys


print("step 1: caches (v2 first build is slow - codecs run real ffmpeg)")
Xtr, ytr = build_cache(train_rows, "train", "aug")        # v2 training data
Xdv, ydv = build_cache(dev_rows,   "dev",   "clean")
Xe_cl, ye_cl = build_cache(eval_rows, "eval", "clean")
Xe_mu, ye_mu = build_cache(eval_rows, "eval", "mulaw")    # landline test
Xe_op, ye_op = build_cache(eval_rows, "eval", "opus16")   # whatsapp test


def clip_to_tensor(x):
    x = x.astype(np.float32)
    x = (x - x.mean()) / (x.std() + 1e-6)
    return torch.from_numpy(x[None, ...])


def train_model(X, y):
    model = MelCNN()
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    lossfn = nn.BCEWithLogitsLoss()
    loader = torch.utils.data.DataLoader(
        [(clip_to_tensor(X[i]), float(y[i])) for i in range(len(y))],
        batch_size=BATCH, shuffle=True)
    print(f"training {EPOCHS} epochs on {len(y)} clips ...")
    for ep in range(1, EPOCHS + 1):
        model.train()
        tot = nb = 0
        t0 = time.time()
        for xb, yb in loader:
            opt.zero_grad()
            loss = lossfn(model(xb), yb)
            loss.backward()
            opt.step()
            tot += loss.item(); nb += 1
        print(f"  epoch {ep:2d}/{EPOCHS}  loss {tot/nb:.4f}  ({time.time()-t0:.0f}s)")
    return model


@torch.no_grad()
def score(model, X, y):
    model.eval()
    out = []
    for i in range(0, len(y), BATCH):
        xb = torch.from_numpy(np.stack([clip_to_tensor(X[j]) for j in range(i, min(i + BATCH, len(y)))]))
        out.append(torch.sigmoid(model(xb)).numpy())
    return np.concatenate(out)


def eer_of(scores, labels):
    fpr, tpr, _ = roc_curve(labels, scores)
    return float(fpr[np.nanargmin(np.abs(fpr - (1 - tpr)))])


print("step 2: train v2 (codec-hardened)")
v2 = train_model(Xtr, ytr)

os.makedirs(OUT_DIR, exist_ok=True)
torch.save(v2.state_dict(), os.path.join(OUT_DIR, "model.pt"))

models = {"v2 (codec-augmented)": v2}
if os.path.exists(V1_MODEL):
    v1 = MelCNN()
    v1.load_state_dict(torch.load(V1_MODEL, map_location="cpu"))
    models = {"v1 (clean-trained)": v1, **models}
else:
    print("(v1 model not found - comparing v2 only)")

conds = [("clean", Xe_cl, ye_cl), ("landline mulaw", Xe_mu, ye_mu),
         ("whatsapp opus16", Xe_op, ye_op)]

print()
print("=" * 74)
print("THE ROBUSTNESS TABLE (eval EER %, unseen attacks - lower is better)")
print("=" * 74)
header = f"{'model':24s}" + "".join(f"{c[0]:>18s}" for c in conds)
print(header)
print("-" * 74)
table = {}
for mname, model in models.items():
    eers = []
    for cname, X, y in conds:
        e = eer_of(score(model, X, y), np.asarray(y))
        eers.append(e)
    table[mname] = [round(e, 4) for e in eers]
    print(f"{mname:24s}" + "".join(f"{e*100:17.1f}%" for e in eers))

for mname, model in models.items():
    d = eer_of(score(model, Xdv, ydv), np.asarray(ydv))
    print(f"   {mname}: dev (seen attacks, clean) EER {d*100:.1f}%")

json.dump({"robustness_eer": table,
           "note": "v2 trained with 50% real-codec augmentation; caps as in v1"},
          open(os.path.join(OUT_DIR, "metrics.json"), "w"), indent=2)

print()
print("saved:", OUT_DIR)
print("V2 DONE - paste this table to the mentor")