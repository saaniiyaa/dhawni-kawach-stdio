# 1_record_voice.py
# Records 8 seconds from your microphone and saves it as data/my_voice.wav

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))   # always work from the project folder

import time

import sounddevice as sd
import soundfile as sf

SECONDS = 8
SR = 16000

print("Ready to record", SECONDS, "seconds at", SR, "samples per second.")
print("Say something normal, like:")
print("   'Hi, this is my real voice. I am testing Dhwani Kavach today.'")
print()

for count in [3, 2, 1]:
    print(count, "...")
    time.sleep(1)

print("RECORDING ... speak now")

try:
    audio = sd.rec(int(SECONDS * SR), samplerate=SR, channels=1, dtype="float32")
    sd.wait()   # wait here until recording is finished
except Exception as err:
    print()
    print("Could not open the microphone.")
    print("Reason:", err)
    print("Check: mic is connected, and Windows Settings > Privacy & security > Microphone is ON.")
    raise SystemExit(1)

os.makedirs("data", exist_ok=True)
sf.write("data/my_voice.wav", audio, SR, subtype="PCM_16")

peak = float(abs(audio).max())
print()
print("Saved         : data/my_voice.wav")
print("loudest value :", round(peak, 3))
if peak < 0.02:
    print("WARNING: recording is very quiet. Speak louder / sit closer to the mic and run again.")
else:
    print("Recording looks good. Now open 1_test_audio.py and click Run.")
    