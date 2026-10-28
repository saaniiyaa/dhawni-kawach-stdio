# 5_record_team.py  (v2)
# Records 60 seconds for EACH person -> data/team/<name>.wav
# WHY this file matters NOW: our model has never heard Indian voices on a
# laptop mic - that is why it called your real voice "risky" (score 0.73).
# These recordings are step 1 of the fix: they show us what REAL voices
# score on this machine, so we can re-set the warning line (Block 10).

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import subprocess
import sys
import time

try:
    import sounddevice as sd
except ImportError:
    print("sounddevice missing - installing it once (about 30 seconds)...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "sounddevice"])
    import sounddevice as sd

import soundfile as sf

SR = 16000
SECONDS = 60

os.makedirs("data/team", exist_ok=True)

print("TEAM + FAMILY VOICE RECORDING  (60 seconds per person)")
print("WHAT TO SAY: describe your day / talk about anything - Hindi, English, mix.")
print("A HINGLISH MIX IS PERFECT - that is exactly the sound we need.")
print("Speak one at a time. Pass the laptop around.")
print()


def record(seconds):
    """Try the mic at 16 kHz; if the device refuses, use its own rate and resample."""
    try:
        audio = sd.rec(int(seconds * SR), samplerate=SR, channels=1, dtype="float32")
        sd.wait()
        return audio
    except Exception:
        import librosa
        dev_sr = int(sd.query_devices(kind="input")["default_samplerate"])
        audio = sd.rec(int(seconds * dev_sr), samplerate=dev_sr, channels=1, dtype="float32")
        sd.wait()
        y = librosa.resample(audio[:, 0], orig_sr=dev_sr, target_sr=SR)
        return y.reshape(-1, 1)


while True:
    name = input("Type this person's name (or press Enter alone to finish): ").strip()
    if not name:
        break

    safe = "".join(c for c in name if c.isalnum() or c in " _-").strip().replace(" ", "_")
    if not safe:
        print("Name empty after cleaning - try again.")
        continue

    out_path = os.path.join("data", "team", safe + ".wav")
    print()
    print(f"Get ready, {safe}: speak NATURALLY for {SECONDS} seconds.")
    print("Idea: 'Aaj maine kya kiya...' - just talk, do not read a script.")
    for count in [3, 2, 1]:
        print(count, "...")
        time.sleep(1)
    print("RECORDING ... speak now")

    try:
        audio = record(SECONDS)
    except Exception as err:
        print("Microphone problem:", err)
        print("Fix the mic and type the name again.")
        continue

    sf.write(out_path, audio, SR, subtype="PCM_16")
    peak = float(abs(audio).max())
    note = "OK" if peak >= 0.05 else "TOO QUIET - please record again, louder"
    print(f"Saved {out_path}   loudest value: {peak:.3f}   {note}")
    print()

print()
print("Recording session finished. Files are in: data/team/")
print("NEXT STEP: run 12_check_my_voice.py - it also scores these files now,")
print("and those numbers are what we use to re-set the warning line.")