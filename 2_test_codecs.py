# 2_test_codecs.py
# Takes YOUR voice, pushes it through simulated phone/WhatsApp networks,
# and shows exactly what evidence gets destroyed.

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))   # always work from project folder

import glob

import numpy as np
import matplotlib
matplotlib.use("Agg")            # draw pictures to files, no window needed
import matplotlib.pyplot as plt

from ml.audio.io import load, SR
from ml.augment.codecs import available, apply_codec

# ---- find your voice file automatically ----
candidates = sorted(glob.glob("data/*.wav")) + sorted(glob.glob("data/*.flac"))
if not candidates:
    print("NO AUDIO FILE in data/ - run 1_record_voice.py first")
    raise SystemExit(0)

FILE = candidates[0]
print("Using file   :", FILE)
print()

y = load(FILE)


# ---- tiny measurer: how much sound energy lives in the high frequencies ----
def highband(audio, sr, lo_hz):
    Y = np.abs(np.fft.rfft(audio)) ** 2                    # energy per frequency
    freqs = np.fft.rfftfreq(len(audio), 1.0 / sr)          # frequency labels
    total = Y.sum() + 1e-12
    return float(Y[freqs >= lo_hz].sum() / total)


# ---- push your voice through every available codec ----
conds = [("original", y)]
for name in available():
    print("processing", name, "...")
    out, _ = apply_codec(y, SR, name, tag="myvoice")
    conds.append((name, out))

# ---- the damage table ----
print()
print("condition    energy>4kHz   energy>6kHz")
for name, audio in conds:
    print(f"{name:10s} {highband(audio, SR, 4000):12.5f} {highband(audio, SR, 6000):12.5f}")

# ---- picture: one spectrogram per condition ----
n = len(conds)
fig, axes = plt.subplots(n, 1, figsize=(8, 2.2 * n), sharex=True)
if n == 1:
    axes = [axes]

for ax, (name, audio) in zip(axes, conds):
    ax.specgram(audio, NFFT=1024, Fs=SR, noverlap=768, cmap="magma")
    ax.set_ylabel(name, rotation=0, ha="right", va="center")
    ax.set_ylim(0, 8000)
    ax.axhline(3400, color="cyan", lw=1, ls="--")   # the phone-line ceiling

axes[0].set_title("What phone/WhatsApp codecs do to YOUR voice  (cyan line = 3400 Hz phone limit)")
axes[-1].set_xlabel("seconds")

os.makedirs("results/codec_test", exist_ok=True)
out_png = "results/codec_test/codec_panel.png"
plt.tight_layout()
plt.savefig(out_png, dpi=110)

print()
print("Saved picture :", out_png)
print("Saved audio   : results/codec_test/myvoice_<codec>_16k.wav   <- PLAY THESE")
print()
print("CODEC TEST DONE")