# 3_test_features.py
# Computes the 20 voice-vitals for THREE versions of your voice:
#   original / after landline (mulaw) / after WhatsApp (opus)
# Shows which vitals survive the phone network and which get destroyed.

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))   # always work from project folder

import glob
import csv

from ml.audio.io import load, SR
from ml.features.dsp import named_features, FEATURE_NAMES
from ml.augment.codecs import apply_codec

# ---- find your voice ----
candidates = sorted(glob.glob("data/*.wav")) + sorted(glob.glob("data/*.flac"))
if not candidates:
    print("NO AUDIO FILE in data/ - run 1_record_voice.py first")
    raise SystemExit(0)

y_orig = load(candidates[0])
print("Using file :", candidates[0])
print()

# ---- get the phone versions (reuse Block 3 files if present, else make them) ----
def get_condition(name, fname):
    path = os.path.join("results", "codec_test", fname)
    if os.path.exists(path):
        return load(path)
    out, _ = apply_codec(y_orig, SR, name, tag="myvoice")
    return out

y_mulaw = get_condition("mulaw", "myvoice_mulaw_16k.wav")
y_opus = get_condition("opus16", "myvoice_opus16_16k.wav")

# ---- measure all three ----
print("measuring original / landline / whatsapp versions ...")
f_orig = named_features(y_orig)
f_mulaw = named_features(y_mulaw)
f_opus = named_features(y_opus)

assert len(f_orig) == 20, "expected 20 features, got " + str(len(f_orig))

# ---- print the comparison table ----
print()
print(f"{'feature':24s} {'original':>12s} {'landline':>12s} {'whatsapp':>12s}")
print("-" * 62)
for name in FEATURE_NAMES:
    a, b, c = f_orig[name], f_mulaw[name], f_opus[name]
    print(f"{name:24s} {a:12.5g} {b:12.5g} {c:12.5g}")

# ---- save as CSV for later use / PPT ----
os.makedirs("results/feature_test", exist_ok=True)
with open("results/feature_test/features.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["feature", "original", "landline_mulaw", "whatsapp_opus16"])
    for name in FEATURE_NAMES:
        w.writerow([name, f_orig[name], f_mulaw[name], f_opus[name]])

print()
print("Saved table  : results/feature_test/features.csv")
print("FEATURE TEST DONE")