# 4_train_toy_ai.py
# YOUR FIRST AI. Toy experiment on your own voice.
# Real examples  = pieces of your voice
# Fake examples  = your voice pushed through 3 toy 'clone simulators' (A, B, C)
# The model trains on generators A and B only, and on HALF your windows.
# Then we test on the OTHER half (never trained on):
#   - reals + A + B   (generator seen before)  -> should be easy
#   - reals + C       (generator NEVER seen)   -> the honest test

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import glob
import numpy as np
from scipy.signal import resample_poly

from ml.audio.io import load, SR, energy_vad, rms_normalize
from ml.features.dsp import named_features, FEATURE_NAMES

rng = np.random.default_rng(42)

WIN = 3 * SR          # 3-second pieces
N_WINDOWS = 40        # 20 for training, 20 for testing


# ---------- helpers ----------

def random_speech_window(y, tries=60):
    """Cut a random 3 s piece that actually contains speech."""
    if len(y) <= WIN:
        reps = int(np.ceil(WIN / len(y)))
        y = np.tile(y, reps)
    for _ in range(tries):
        start = rng.integers(0, len(y) - WIN + 1)
        piece = y[start:start + WIN]
        if energy_vad(piece).mean() > 0.25:      # enough speech inside?
            return piece.copy()
    return y[:WIN].copy()


def toy_A_phoneghost(y):
    """Simulated cheap TTS over phone: everything above 4 kHz deleted."""
    return rms_normalize(resample_poly(resample_poly(y, 1, 2), 2, 1))


def toy_B_metalbox(y):
    """Metallic comb-filter robot: add a delayed copy of the voice to itself."""
    d = int(0.012 * SR)                            # 12 ms delay
    out = y.copy()
    out[d:] += 0.55 * y[:-d]
    return rms_normalize(np.tanh(1.2 * out))       # soft clip


def toy_C_smoothie(y):
    """SUBTLE over-smoothed vocoder: light time-smear, blended with the
    original. On purpose - a too-obvious fake would make the toy trivial."""
    import librosa
    S = librosa.stft(y, n_fft=512, hop_length=160)
    k = 5                                           # smoothing width in frames
    Sm = np.copy(S)
    for i in range(len(S[0])):
        lo, hi = max(0, i - k // 2), min(len(S[0]), i + k // 2 + 1)
        Sm[:, i] = S[:, lo:hi].mean(axis=1)         # average magnitudes over time
    smoothed = librosa.istft(Sm, hop_length=160)
    return rms_normalize(0.5 * smoothed + 0.5 * y)  # half fake, half real: sneaky


def make_real(w):
    """A 'real' example: your voice with random loudness + soft room noise."""
    w2 = w * (10 ** (rng.uniform(-6, 6) / 20))              # bigger loudness range
    w2 = w2 + rng.normal(0, rng.uniform(0.002, 0.008), len(w2))
    return rms_normalize(w2)


# ---------- load your voice ----------

candidates = sorted(glob.glob("data/*.wav")) + sorted(glob.glob("data/*.flac"))
if not candidates:
    print("NO AUDIO FILE in data/ - run 1_record_voice.py first")
    raise SystemExit(0)

voice = load(candidates[0])
print("Using file :", candidates[0])


# ---------- build the toy dataset ----------

print("cutting", N_WINDOWS, "speech windows from your voice ...")
windows = [random_speech_window(voice) for _ in range(N_WINDOWS)]
train_w = windows[: N_WINDOWS // 2]                  # first half for training
test_w = windows[N_WINDOWS // 2:]                    # second half for testing

examples = []   # each item: (audio, label, generator, group)
for w in train_w:
    examples.append((make_real(w), 0, "real", "train"))
    examples.append((toy_A_phoneghost(w), 1, "A", "train"))
    examples.append((toy_B_metalbox(w), 1, "B", "train"))
for w in test_w:
    examples.append((make_real(w), 0, "real", "test"))
    examples.append((toy_A_phoneghost(w), 1, "A", "test"))
    examples.append((toy_B_metalbox(w), 1, "B", "test"))
    examples.append((toy_C_smoothie(w), 1, "C", "test"))

# note: generator C is created ONLY for the test group - the model never sees it


# ---------- compute the 20 features for every example ----------

print("measuring 20 features per example (slow part, ~1-2 min on a laptop) ...")
Feat = np.array([[f for f in named_features(x).values()] for x, *_ in examples])
labels = np.array([lab for _, lab, _, _ in examples])
gens = np.array([g for _, _, g, _ in examples])
groups = np.array([gr for _, _, _, gr in examples])
print("dataset:", Feat.shape[0], "examples x", Feat.shape[1], "features")


# ---------- train on: group=train  (reals + A + B) ----------

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_curve

train_idx = np.where(groups == "train")[0]
seen_idx = np.where((groups == "test") & (gens != "C"))[0]        # test reals + A + B
unseen_idx = np.where((groups == "test") & ((gens == "C") | (gens == "real")))[0]

print("training GradientBoosting model ...")
model = GradientBoostingClassifier(n_estimators=120, max_depth=3, random_state=42)
model.fit(Feat[train_idx], labels[train_idx])


def eer_of(scores, y):
    """Error rate where false-accept = false-reject. 0=perfect, 50=coin toss."""
    fpr, tpr, _ = roc_curve(y, scores)
    return 100.0 * float(fpr[np.nanargmin(np.abs(fpr - tpr))])


scores = model.predict_proba(Feat)[:, 1]

eer_seen = eer_of(scores[seen_idx], labels[seen_idx])
eer_unseen = eer_of(scores[unseen_idx], labels[unseen_idx])
acc_seen = 100.0 * float(((scores[seen_idx] >= 0.5) == labels[seen_idx]).mean())
acc_unseen = 100.0 * float(((scores[unseen_idx] >= 0.5) == labels[unseen_idx]).mean())

print()
print("================ TOY RESULTS ================")
print(f"seen generators (A, B)   : EER {eer_seen:5.1f}%   accuracy {acc_seen:5.1f}%")
print(f"UNSEEN generator (C)     : EER {eer_unseen:5.1f}%   accuracy {acc_unseen:5.1f}%")
print("=============================================")
print()
print("What the model leaned on (top 5 features):")
order = np.argsort(model.feature_importances_)[::-1]
for i in order[:5]:
    print(f"   {FEATURE_NAMES[i]:24s} {100*model.feature_importances_[i]:5.1f}%")

os.makedirs("results/toy_ai", exist_ok=True)
with open("results/toy_ai/summary.txt", "w") as fh:
    fh.write("TOY EXPERIMENT - 1 speaker, simulated generators, tiny set\n")
    fh.write("These numbers prove the PIPELINE works. They are NOT detection performance.\n")
    fh.write(f"seen   A,B : EER {eer_seen:.1f}%  acc {acc_seen:.1f}%\n")
    fh.write(f"unseen C   : EER {eer_unseen:.1f}%  acc {acc_unseen:.1f}%\n")

print()
print("Saved: results/toy_ai/summary.txt")
print("TOY AI DONE")