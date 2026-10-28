# 0_check_setup.py
# One-look health check: right Python? all libraries present?

import sys

print("python  :", sys.executable)      # MUST contain .venv in the path
print("version :", sys.version.split()[0])
print()

missing = []
for name in ["numpy", "scipy", "librosa", "soundfile", "sklearn",
             "yaml", "torch", "flask", "sounddevice"]:
    try:
        mod = __import__(name)
        v = getattr(mod, "__version__", "ok")
        print(f"{name:12s}: {v}")
    except ImportError:
        missing.append(name)
        print(f"{name:12s}: MISSING")

try:
    import imageio_ffmpeg
    print("ffmpeg      :", imageio_ffmpeg.get_ffmpeg_exe())
except ImportError:
    missing.append("imageio-ffmpeg")
    print("ffmpeg      : MISSING")

print()
if missing:
    print("MISSING:", ", ".join(missing))
    print("Tell the mentor which ones - do not install randomly.")
else:
    print("SETUP OK - everything present, correct environment")