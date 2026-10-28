import numpy as np
import soundfile as sf
import librosa

SR = 16000   # every audio in this project is 16,000 samples per second


def load(path, sr=SR):
    y, _ = librosa.load(path, sr=sr, mono=True)
    return y.astype(np.float32)


def save(path, y, sr=SR):
    sf.write(path, np.clip(y, -1.0, 1.0), sr, subtype="PCM_16")


def dc_remove(y):
    return y - float(np.mean(y))


def rms_normalize(y, target_dbfs=-23.0):
    rms = float(np.sqrt(np.mean(y ** 2))) + 1e-9
    target = 10 ** (target_dbfs / 20.0)
    out = y * (target / rms)
    return np.clip(out, -1.0, 1.0).astype(np.float32)


def fix_length(y, n):
    if len(y) == n:
        return y
    if len(y) > n:
        return y[:n]
    reps = int(np.ceil(n / max(len(y), 1)))
    return np.tile(y, reps)[:n]


def energy_vad(y, sr=SR, frame_ms=25, hop_ms=10, rel_db=30.0):
    fl = int(sr * frame_ms / 1000)
    hl = int(sr * hop_ms / 1000)
    if len(y) < fl:
        return np.ones(len(y), dtype=bool)
    frames = librosa.util.frame(y, frame_length=fl, hop_length=hl)
    e = 20 * np.log10(np.sqrt(np.mean(frames ** 2, axis=0)) + 1e-9)
    keep = e > (e.max() - rel_db)
    mask = np.zeros(len(y), dtype=bool)
    for i, k in enumerate(keep):
        if k:
            mask[i * hl: i * hl + fl] = True
    return mask