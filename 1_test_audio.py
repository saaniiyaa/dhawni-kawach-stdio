# 1_test_audio.py
# Tests our audio loading functions using the first audio file in the data/ folder.

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))   # always work from the project folder

import glob

from ml.audio.io import load, rms_normalize, energy_vad

# find any audio file in data/ automatically (wav first, then flac, then mp3)
candidates = (
    sorted(glob.glob("data/*.wav"))
    + sorted(glob.glob("data/*.flac"))
    + sorted(glob.glob("data/*.mp3"))
)

if not candidates:
    print("NO AUDIO FILE FOUND in the 'data' folder.")
    print("Fix: open 1_record_voice.py and click Run - it creates data/my_voice.wav")
    raise SystemExit(0)

FILE = candidates[0]
print("Using file   :", FILE)
print()

y = load(FILE)

print("samples          :", len(y))
print("seconds          :", round(len(y) / 16000, 2))
print("loudest value    :", round(float(abs(y).max()), 3))
print("speech fraction  :", round(float(energy_vad(y).mean()), 3))

y2 = rms_normalize(y)
print("after normalise  :", round(float(abs(y2).max()), 3))
print()
print("AUDIO TEST OK")