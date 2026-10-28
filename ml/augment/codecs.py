# ml/augment/codecs.py
# Turns clean 16 kHz audio into "phone call / WhatsApp" quality audio.
# How: we use a REAL ffmpeg binary (it comes bundled inside the imageio-ffmpeg
# package, so nothing extra to install) with the same codecs real networks use.

import os
import subprocess

import numpy as np
import soundfile as sf
import imageio_ffmpeg

from ml.audio.io import SR, rms_normalize

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()   # full path to a real ffmpeg program

# Each recipe = one real-world network condition:
#   mulaw  : classic landline / IVR / call-center audio (8 kHz telephony standard)
#   alaw   : the landline telephony standard used in India/Europe
#   amrnb  : AMR narrowband - voice on 2G/3G mobile networks
#   opus16 : WhatsApp voice notes / VoIP apps (Opus codec at 16 kbps)
#   mp3_64 : compressed audio files shared over the internet
RECIPES = {
    "mulaw":  {"args": ["-ar", "8000", "-acodec", "pcm_mulaw"], "ext": ".wav"},
    "alaw":   {"args": ["-ar", "8000", "-acodec", "pcm_alaw"],  "ext": ".wav"},
    "amrnb":  {"args": ["-ar", "8000", "-acodec", "libopencore_amrnb", "-b:a", "12.2k"], "ext": ".amr"},
    "opus16": {"args": ["-acodec", "libopus", "-b:a", "16k"],    "ext": ".opus"},
    "mp3_64": {"args": ["-acodec", "libmp3lame", "-b:a", "64k"], "ext": ".mp3"},
}


def available():
    """Return which codec names this ffmpeg binary can actually do."""
    out = subprocess.run([FFMPEG, "-hide_banner", "-encoders"],
                         capture_output=True, text=True).stdout
    ok = []
    for name, r in RECIPES.items():
        enc = r["args"][r["args"].index("-acodec") + 1]
        if enc in out:
            ok.append(name)
    return ok


def run_quiet(cmd):
    """Run ffmpeg silently. If it fails, show us the real reason."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + r.stderr[-800:])


def apply_codec(y, sr, name, workdir="results/codec_test", tag="clip"):
    """Compress audio 'y' with codec 'name', then decode it back to normal
    16 kHz audio. Returns (audio, 16000). Keeps the files so you can listen."""
    if name not in RECIPES:
        raise ValueError("unknown codec: " + name)
    os.makedirs(workdir, exist_ok=True)

    clean = os.path.join(workdir, tag + "_in.wav")
    coded = os.path.join(workdir, tag + "_" + name + RECIPES[name]["ext"])
    back = os.path.join(workdir, tag + "_" + name + "_16k.wav")

    sf.write(clean, np.clip(y, -1.0, 1.0), sr, subtype="PCM_16")

    # step 1: compress with the real network codec
    run_quiet([FFMPEG, "-hide_banner", "-y", "-i", clean] + RECIPES[name]["args"] + [coded])
    # step 2: decode back to a plain 16 kHz wav our pipeline can read
    run_quiet([FFMPEG, "-hide_banner", "-y", "-i", coded, "-ar", str(SR), "-ac", "1", back])

    out, sr_out = sf.read(back, dtype="float32")
    if out.ndim > 1:          # stereo safety: keep one channel
        out = out[:, 0]
    return rms_normalize(out), sr_out