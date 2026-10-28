# 7_train_cnn.py
# BLOCK 7 - train the REAL detector (version 1) on ASVspoof 2019 LA.
#   1. reads our manifest.csv (made by 6_build_manifest.py)
#   2. takes a CAPPED sample of clips (so a normal laptop survives)
#   3. log-mel spectrograms, CACHED to disk (first run slow, then fast)
#   4. trains the small CNN (ml/models/cnn.py) on the train split
#   5. scores dev (seen attacks) and eval (UNSEEN attacks A07-A19)
#   6. saves model + metrics into results/cnn_v1/
# v1 = honest baseline: no codec augmentation yet (that is Block 8).

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))   # always work from project folder

import csv
import json
import random
import time

import numpy as np

MANIFEST = os.path.join("data", "processed", "asvspoof19la", "manifest.csv")
CACHE    = os.path.join("data", "cache", "cnn_v1")
OUT_DIR  = os.path.join("results", "cnn_v1")

SECONDS = 4.0                       # every clip is cut/padded to 4 s
MAX_REAL_TR, MAX_FAKE_TR = 2000, 2000
MAX_DEV, MAX_EVAL        = 800, 1200
EPOCHS, BATCH, LR        = 10, 16, 1e-3
SEED = 1234

random.seed(SEED)
np.random.seed(SEED)

# ---------- step 0: friendly checks ----------

if not os.path.exists(MANIFEST):
    print("Manifest not found:", MANIFEST)
    print("Run 6_build_manifest.py first.")
    raise SystemExit(0)

try:
    import torch
    import torch.nn as nn
except ImportError:
    print("torch not installed in this venv.")
    print("Fix: requirements.txt must contain 'torch', then recreate the environment.")
    raise SystemExit(0)

from sklearn.metrics import roc_curve

from ml.audio.io import load, SR, fix_length
from ml.features.dsp import logmel
from ml.models.cnn import MelCNN, count_params

torch.manual_seed(SEED)
torch.set_num_threads(2)
N_FRAMES = logmel(np.zeros(int(SECONDS * SR), dtype=np.float32)).shape[1]

# ---------- step 1: read manifest, cap samples ----------

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
print(f"using: train {len(train_rows)} | dev {len(dev_rows)} | eval {len(eval_rows)} clips")

# ---------- step 2: build / load the feature cache ----------

def build_cache(split_rows, tag):
    x_path = os.path.join(CACHE, f"X_{tag}.npy")
    if os.path.exists(x_path):
        print(f"cache found for {tag} - reusing (delete the folder to rebuild)")
        X = np.load(x_path, mmap_mode="r")
        return X, np.load(os.path.join(CACHE, f"y_{tag}.npy")), \
               np.load(os.path.join(CACHE, f"a_{tag}.npy"), allow_pickle=True)

    os.makedirs(CACHE, exist_ok=True)
    N = len(split_rows)
    X = np.lib.format.open_memmap(x_path, mode="w+", dtype=np.float16,
                                  shape=(N, 80, N_FRAMES))
    ys, atks = [], []
    t0 = time.time()
    for i, r in enumerate(split_rows):
        aud = fix_length(load(r["path"]), int(SECONDS * SR))
        X[i] = logmel(aud).astype(np.float16)
        ys.append(1 if r["label"] == "spoof" else 0)
        atks.append(r["attack"])
        if (i + 1) % 100 == 0:
            speed = (i + 1) / max(time.time() - t0, 0.01)
            print(f"  {tag}: {i+1}/{N}  ({speed:.1f} clips/s, ~{(N-i-1)/speed/60:.1f} min left)")
    X.flush()
    ys, atks = np.array(ys), np.array(atks)
    np.save(os.path.join(CACHE, f"y_{tag}.npy"), ys)
    np.save(os.path.join(CACHE, f"a_{tag}.npy"), atks)
    return X, ys, atks

print("step 2: feature caches (first run takes ~15-25 min - grab chai)")
Xtr, ytr, atr = build_cache(train_rows, "train")
Xdv, ydv, adv = build_cache(dev_rows,   "dev")
Xev, yev, aev = build_cache(eval_rows,  "eval")

# ---------- step 3: torch data ----------

def clip_to_tensor(x):
    x = x.astype(np.float32)
    x = (x - x.mean()) / (x.std() + 1e-6)      # per-clip normalisation
    return torch.from_numpy(x[None, ...])

class CacheSet(torch.utils.data.Dataset):
    def __init__(self, X, y):
        self.X, self.y = X, np.asarray(y)
    def __len__(self):
        return len(self.y)
    def __getitem__(self, i):
        return clip_to_tensor(self.X[i]), float(self.y[i])

train_loader = torch.utils.data.DataLoader(CacheSet(Xtr, ytr), batch_size=BATCH,
                                           shuffle=True, num_workers=0)

# ---------- step 4: train ----------

model = MelCNN()
print(f"model parameters: {count_params(model):,}")
opt = torch.optim.Adam(model.parameters(), lr=LR)
lossfn = nn.BCEWithLogitsLoss()

print(f"step 3: training {EPOCHS} epochs on {len(ytr)} clips (CPU)")
for ep in range(1, EPOCHS + 1):
    model.train()
    tot = nb = 0
    t0 = time.time()
    for xb, yb in train_loader:
        opt.zero_grad()
        loss = lossfn(model(xb), yb)
        loss.backward()
        opt.step()
        tot += loss.item(); nb += 1
    print(f"  epoch {ep:2d}/{EPOCHS}  loss {tot/nb:.4f}  ({time.time()-t0:.0f}s)")

# ---------- step 5: scoring + metrics ----------

@torch.no_grad()
def score_split(X, y):
    model.eval()
    out = []
    for i in range(0, len(y), BATCH):
        xb = torch.from_numpy(np.stack([clip_to_tensor(X[j]) for j in range(i, min(i + BATCH, len(y)))]))
        out.append(torch.sigmoid(model(xb)).numpy())
    return np.concatenate(out)

def eer_of(scores, labels):
    fpr, tpr, _ = roc_curve(labels, scores)
    return float(fpr[np.nanargmin(np.abs(fpr - (1 - tpr)))])

s_dv = score_split(Xdv, ydv)
s_ev = score_split(Xev, yev)
ydv, yev = np.asarray(ydv), np.asarray(yev)

eer_dev, eer_eval = eer_of(s_dv, ydv), eer_of(s_ev, yev)
acc_dev  = float(((s_dv >= 0.5) == ydv).mean())
acc_eval = float(((s_ev >= 0.5) == yev).mean())

# per unseen attack: which attack families fool us?
# (each attack's fakes vs ALL eval reals - a fair two-class test)
per_attack = {}
reals = aev == "none"
for a in sorted(set(aev.tolist()) - {"none"}):
    m = (aev == a) | reals
    if m.sum() >= 10:
        per_attack[str(a)] = round(eer_of(s_ev[m], yev[m]), 4)

# TPR at 1% false-alarm on dev (with honesty guard)
n_neg = int((ydv == 0).sum())
if n_neg >= 100:
    th = np.quantile(s_dv[ydv == 0], 0.99)
    tpr_1pct = round(float((s_dv[ydv == 1] >= th).mean()), 4)
else:
    tpr_1pct = "NOT MEASURABLE (dev negatives < 100)"

# ---------- step 6: save ----------

os.makedirs(OUT_DIR, exist_ok=True)
torch.save(model.state_dict(), os.path.join(OUT_DIR, "model.pt"))
json.dump({
    "version": "cnn_v1 (no augmentation, capped subsets)",
    "n_train": int(len(ytr)), "n_dev": int(len(ydv)), "n_eval": int(len(yev)),
    "eer_dev_seen": round(eer_dev, 4), "eer_eval_unseen": round(eer_eval, 4),
    "acc_dev": round(acc_dev, 4), "acc_eval": round(acc_eval, 4),
    "tpr_at_fpr1pct_dev": tpr_1pct,
    "eer_eval_per_attack": per_attack,
    "note": "subset caps: train<=4000 dev<=800 eval<=1200; full runs later",
}, open(os.path.join(OUT_DIR, "metrics.json"), "w"), indent=2)

print()
print("=" * 62)
print("V1 RESULTS (subsets, no augmentation - the honest baseline)")
print("=" * 62)
print(f"dev  (SEEN attacks)    EER {eer_dev*100:5.1f}%   acc {acc_dev*100:5.1f}%")
print(f"eval (UNSEEN attacks)  EER {eer_eval*100:5.1f}%   acc {acc_eval*100:5.1f}%")
print(f"dev  TPR @ 1% false-alarm: {tpr_1pct if isinstance(tpr_1pct, str) else str(tpr_1pct*100) + '%'}")
print()
print("per unseen attack (attack fakes vs eval reals):")
for a, e in sorted(per_attack.items()):
    print(f"   {a} : EER {e*100:5.1f}%")
print()
print("saved:", OUT_DIR, "(model.pt + metrics.json)")
print("TRAINING DONE")