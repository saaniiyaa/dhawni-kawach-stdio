# 6z3_protocol_doctor.py
# DOCTOR: looks INSIDE the three protocol files and reports exactly what's wrong.

import os

HOME = os.path.expanduser("~")
POSSIBLE_ROOTS = [
    r"C:\dhwani_data\LA\LA",
    r"C:\dhwani_data\LA",
    r"C:\dhwani_data",
    os.path.join(HOME, "Downloads", "LA"),
]

PROTOCOLS = {
    "train": "ASVspoof2019_LA_cm_protocols/ASVspoof2019.LA.cm.train.trn.txt",
    "dev":   "ASVspoof2019_LA_cm_protocols/ASVspoof2019.LA.cm.dev.trl.txt",
    "eval":  "ASVspoof2019_LA_cm_protocols/ASVspoof2019.LA.cm.eval.trl.txt",
}
FLAC_DIRS = {
    "train": "ASVspoof2019_LA_train/flac",
    "dev":   "ASVspoof2019_LA_dev/flac",
    "eval":  "ASVspoof2019_LA_eval/flac",
}

root = None
for candidate in POSSIBLE_ROOTS:
    if os.path.isdir(os.path.join(candidate, FLAC_DIRS["train"])):
        root = candidate
        break

if root is None:
    print("Could not find the dataset. Run 6z_find_dataset.py again.")
    raise SystemExit(0)

print("dataset root:", root)
print()

for split, rel in PROTOCOLS.items():
    path = os.path.join(root, rel)
    print("=" * 60)
    print(split, "->", path)
    if not os.path.exists(path):
        print("   FILE DOES NOT EXIST")
        continue
    size = os.path.getsize(path)
    print(f"   file size: {size} bytes")
    if size == 0:
        print("   VERDICT: file is EMPTY -> extraction was incomplete. Re-extract LA.zip!")
        continue

    print("   first bytes:", open(path, "rb").read()[:80])

    fields_hist = {}
    n_lines, n_ok = 0, 0
    first_lines = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parts = line.split()
            if not parts:
                continue
            n_lines += 1
            fields_hist[len(parts)] = fields_hist.get(len(parts), 0) + 1
            if len(first_lines) < 3:
                first_lines.append(line.rstrip())
            if parts[-1] in ("bonafide", "spoof"):
                n_ok += 1
    print(f"   non-empty lines: {n_lines}")
    print(f"   columns-per-line histogram: {fields_hist}")
    print(f"   lines ending in bonafide/spoof: {n_ok}")
    print("   first lines:")
    for l in first_lines:
        print("      ", repr(l))

print()
print("=" * 60)
print("FLAC AUDIO COUNTS")
print("=" * 60)
for split, rel in FLAC_DIRS.items():
    d = os.path.join(root, rel)
    if not os.path.isdir(d):
        print(f"{split:5s}: folder MISSING: {d}")
    else:
        try:
            n = len([f for f in os.listdir(d) if f.lower().endswith(".flac")])
        except OSError as err:
            n = f"cannot read ({err})"
        print(f"{split:5s}: {n} .flac files in {d}")

print()
print("Paste this ENTIRE output back to the mentor.")