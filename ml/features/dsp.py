# ml/features/dsp.py
# The 20 "vitals" of a voice.
# Like a doctor measures temperature, BP, pulse -> we measure 20 numbers
# that describe a speech clip. Our AI will later learn which patterns of
# these numbers belong to REAL voices and which to CLONED voices.
# Also here: logmel() - the spectrogram picture our CNN model will look at.

import numpy as np
import librosa

from ml.audio.io import SR, energy_vad

N_FFT = 512      # analysis window: 512 samples = 32 milliseconds
HOP = 160        # slide the window 160 samples = 10 ms each step
N_MELS = 80      # spectrogram height: 80 frequency bands


def logmel(y, sr=SR, n_mels=N_MELS):
    """The spectrogram picture (80 x time) that the CNN head will look at."""
    S = librosa.feature.melspectrogram(y=y, sr=sr, n_fft=N_FFT, hop_length=HOP,
                                       n_mels=n_mels, power=2.0)
    return librosa.power_to_db(S, ref=1.0).astype(np.float32)


def _fft_bands(y, sr):
    """Split energy per frequency. Returns (frequency labels, energies)."""
    Y = np.abs(np.fft.rfft(y)) ** 2
    freqs = np.fft.rfftfreq(len(y), 1.0 / sr)
    return freqs, Y

def _np_pitch(y, sr, fmin=65, fmax=400, frame=1024, hop=160):
    """Standalone numpy autocorrelation F0 (no librosa.yin = no numba DLL)."""
    y = np.asarray(y, dtype=np.float64)
    if len(y) < frame:
        return np.array([])
    lag_min = max(2, int(sr / fmax))
    lag_max = min(int(sr / fmin), frame - 1)
    if lag_max <= lag_min:
        return np.array([])
    n = 1 + (len(y) - frame) // hop
    sz = 1
    while sz < 2 * frame:
        sz *= 2
    out = []
    for i in range(n):
        seg = y[i * hop:i * hop + frame]
        seg = seg - seg.mean()
        if float(np.dot(seg, seg)) < 1e-7:
            continue
        F = np.fft.rfft(seg, sz)
        ac = np.fft.irfft(F * np.conj(F))[:lag_max + 1]
        if ac[0] <= 0:
            continue
        ac = ac / ac[0]
        lag = lag_min + int(np.argmax(ac[lag_min:lag_max + 1]))
        if ac[lag] > 0.30:
            out.append(sr / lag)
    return np.array(out)

def _pitch(y, sr):
    """Track the voice pitch (F0) and return (f0_track, voiced_mask)."""
    f0 = _np_pitch(y, sr)
    rms = librosa.feature.rms(y=y, frame_length=N_FFT, hop_length=HOP)[0]
    n = min(len(f0), len(rms))
    f0, rms = f0[:n], rms[:n]
    voiced = rms > (0.10 * (rms.max() + 1e-9))
    return f0, voiced

    rms = librosa.feature.rms(y=y, frame_length=N_FFT, hop_length=HOP)[0]
    # 'voiced' = frames that are loud enough (simple but works)
    n = min(len(f0), len(rms))
    f0, rms = f0[:n], rms[:n]
    voiced = rms > (0.10 * (rms.max() + 1e-9))
    return f0, voiced


FEATURE_NAMES = [
    # --- frequency shape (7) ---
    "highband_ratio_6k8k",     # fraction of energy in 6-8 kHz
    "highband_ratio_4k6k",     # fraction of energy in 4-6 kHz
    "spectral_rolloff95_hz",   # frequency below which 95% of energy sits
    "spectral_flatness_mean",  # 'buzz vs hiss' - tonal vs noise-like (mean)
    "spectral_flatness_std",   # same, variation over time
    "spectral_centroid_hz",    # the 'brightness' of the sound
    "spectral_bandwidth_hz",   # how spread out the frequencies are
    # --- texture / dynamics (7) ---
    "zcr_mean",                # zero crossing rate - how 'rough' the signal is
    "mfcc1_std",               # variation of timbre (overall sound color)
    "mfcc2_std",               # variation of another timbre dimension
    "delta_mfcc_energy",       # how fast timbre changes - unnatural speed?
    "lowband_energy_db",       # how much energy sits below 1 kHz (in dB)
    "spectral_flux_mean",      # average change of the spectrum over time
    "spectral_flux_std",       # variation of that change
    # --- voice quality (4) ---
    "f0_mean_hz",              # average pitch
    "f0_std_hz",               # pitch movement (real voices vary more)
    "jitter_local",            # tiny cycle-to-cycle pitch wobble (real ~1-2%)
    "voiced_fraction",         # fraction of time with actual voiced speech
    # --- rhythm (2) ---
    "mod_spec_4_8hz",          # energy of syllable rhythm (humans: 4-8 Hz)
    "mod_spec_gt16hz",         # too-fast variation - machines often do this
]


def named_features(y, sr=SR, fast=True):
    """Return a dictionary: {feature_name: value} for one audio clip."""
    out = {}

    # ---- frequency shape ----
    freqs, Y = _fft_bands(y, sr)
    total = Y.sum() + 1e-12
    out["highband_ratio_6k8k"] = float(Y[freqs >= 6000].sum() / total)
    out["highband_ratio_4k6k"] = float(Y[(freqs >= 4000) & (freqs < 6000)].sum() / total)
    out["spectral_rolloff95_hz"] = float(
        librosa.feature.spectral_rolloff(y=y, sr=sr, n_fft=N_FFT, hop_length=HOP,
                                         roll_percent=0.95).mean())
    flat = librosa.feature.spectral_flatness(y=y, n_fft=N_FFT, hop_length=HOP)[0]
    out["spectral_flatness_mean"] = float(flat.mean())
    out["spectral_flatness_std"] = float(flat.std())
    out["spectral_centroid_hz"] = float(
        librosa.feature.spectral_centroid(y=y, sr=sr, n_fft=N_FFT, hop_length=HOP).mean())
    out["spectral_bandwidth_hz"] = float(
        librosa.feature.spectral_bandwidth(y=y, sr=sr, n_fft=N_FFT, hop_length=HOP).mean())

    # ---- texture / dynamics ----
    out["zcr_mean"] = float(
        librosa.feature.zero_crossing_rate(y, frame_length=N_FFT, hop_length=HOP).mean())
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20, n_fft=N_FFT, hop_length=HOP)
    out["mfcc1_std"] = float(mfcc[0].std())
    out["mfcc2_std"] = float(mfcc[1].std())
    d = np.diff(mfcc, axis=1)
    out["delta_mfcc_energy"] = float((d ** 2).mean())
    out["lowband_energy_db"] = float(10 * np.log10((Y[freqs < 1000].sum() + 1e-12) / total))
    S = np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=HOP))
    flux = np.maximum(np.diff(np.log1p(S), axis=1), 0).sum(axis=0)
    out["spectral_flux_mean"] = float(flux.mean())
    out["spectral_flux_std"] = float(flux.std())

    # ---- voice quality ----
    f0, voiced = _pitch(y, sr)
    fv = f0[voiced]
    if len(fv) >= 5:
        out["f0_mean_hz"] = float(fv.mean())
        out["f0_std_hz"] = float(fv.std())
        out["jitter_local"] = float(np.abs(np.diff(fv)).mean() / (fv.mean() + 1e-9))
    else:
        out["f0_mean_hz"] = 0.0
        out["f0_std_hz"] = 0.0
        out["jitter_local"] = 0.0
    out["voiced_fraction"] = float(energy_vad(y, sr).mean())

    # ---- rhythm (modulation spectrum) ----
    env = librosa.feature.rms(y=y, frame_length=N_FFT, hop_length=HOP)[0]
    env = (env - env.mean()) / (env.std() + 1e-9)
    P = np.abs(np.fft.rfft(env)) ** 2
    efreq = np.fft.rfftfreq(len(env), HOP / sr)
    etotal = P.sum() + 1e-12
    out["mod_spec_4_8hz"] = float(P[(efreq >= 4) & (efreq <= 8)].sum() / etotal)
    out["mod_spec_gt16hz"] = float(P[efreq > 16].sum() / etotal)

    return out