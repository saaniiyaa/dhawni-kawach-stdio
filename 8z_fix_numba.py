# 8z_fix_numba.py
# REPAIR: numba's compiled files are broken. This script:
#   Plan A - forces pip to download a FRESH copy of numba
#   Plan B - if still broken, upgrades numpy+numba to a matching pair
#   Plan C - prints manual steps to rebuild the venv (always works)

import subprocess
import sys


def run(cmd):
    print("RUNNING:", " ".join(cmd))
    r = subprocess.run(cmd)
    return r.returncode == 0


print("=" * 60)
print("PLAN A: reinstall a fresh copy of numba (~1 min)")
print("=" * 60)
run([sys.executable, "-m", "pip", "install", "--force-reinstall",
     "--no-cache-dir", "numba"])

print()
print("=" * 60)
print("CHECK: does numba import now?")
print("=" * 60)
ok = False
try:
    import numpy
    import numba
    print("numpy :", numpy.__version__)
    print("numba :", numba.__version__)
    ok = True
except Exception as e:
    print("still broken:", type(e).__name__, "->", e)

if ok:
    print()
    print("checking librosa ...")
    try:
        import librosa
        print("librosa:", librosa.__version__)
        print()
        print("ALL GOOD. Now run 8_train_cnn_v2.py again.")
        raise SystemExit(0)
    except Exception as e:
        print("numba OK but librosa still fails:", e)
        print("Send this full output to the mentor.")
        raise SystemExit(0)

print()
print("=" * 60)
print("PLAN B: align numpy + numba to a matching pair")
print("=" * 60)
run([sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir",
     "numba", "numpy"])
try:
    import numpy
    import numba
    import librosa
    print()
    print("numpy", numpy.__version__, "| numba", numba.__version__,
          "| librosa", librosa.__version__)
    print("ALL GOOD. Now run 8_train_cnn_v2.py again.")
except Exception as e:
    print()
    print("still broken after Plan B:", e)
    print()
    print("=" * 60)
    print("PLAN C (always works, ~10 min) - rebuild the venv:")
    print("=" * 60)
    print(" 1. Pause OneDrive (cloud icon -> Help & Settings -> Pause syncing)")
    print(" 2. File Explorer -> your project -> RIGHT-CLICK the .venv folder -> Delete")
    print(" 3. VS Code -> Ctrl+Shift+P -> 'Python: Create Environment'")
    print("    -> Venv -> Python 3.11 -> TICK requirements.txt -> Create")
    print(" 4. Wait for it to finish (~10 min), then:")
    print("    run 0b_install_sounddevice.py  (adds sounddevice)")
    print("    run 8_train_cnn_v2.py again")