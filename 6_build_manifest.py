# 6_build_manifest.py
# Turns ASVspoof 2019 LA into OUR table (manifest.csv), with sanity checks.

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import csv
import random

from ml.datasets.asvspoof19 import LA_ROOT, check_layout, parse_protocol

random.seed(42)

problems = check_layout(LA_ROOT)
if problems:
    print("DATASET FOLDER PROBLEM:")
    for p in problems:
        print("  -", p)
    print()
    print("Run 6z_find_dataset.py to locate the dataset folder.")
    raise SystemExit(0)

print("Dataset folder found:", LA_ROOT)
print()

all_rows = []
try:
    for split in ["train", "dev", "eval"]:
        rows = parse_protocol(LA_ROOT, split)
        all_rows.extend(rows)
        n_real = sum(1 for r in rows if r["label"] == "bonafide")
        n_fake = sum(1 for r in rows if r["label"] == "spoof")
        speakers = sorted(set(r["speaker"] for r in rows))
        attacks = sorted(set(r["attack"] for r in rows if r["label"] == "spoof"))
        print(f"{split:5s}: {len(rows):6d} clips | {n_real:5d} real | {n_fake:6d} fake "
              f"| {len(speakers):2d} speakers | attacks: {', '.join(attacks)}")
except FileNotFoundError as err:
    print("A protocol file is missing:", err)
    print("The extraction looks incomplete - re-extract LA.zip.")
    raise SystemExit(0)

if not all_rows:
    print()
    print("PROTOCOL FILES PARSED TO 0 ROWS.")
    print("The text files exist but their contents did not parse.")
    print("Run 6z3_protocol_doctor.py and send its FULL output to the mentor.")
    raise SystemExit(0)

print()

sample = random.sample(all_rows, min(20, len(all_rows)))
missing = [r["path"] for r in sample if not os.path.exists(r["path"])]
if missing:
    print("PROBLEM: some audio files listed in the protocol do not exist, e.g.:")
    for m in missing[:5]:
        print("  -", m)
    print()
    print("This means the flac audio files are missing/incomplete - re-extract LA.zip.")
    raise SystemExit(0)
print("File check: random clips found on disk  OK")

def speakers_of(split):
    return set(r["speaker"] for r in all_rows if r["split"] == split)

overlap = (speakers_of("train") & speakers_of("dev")) | \
          (speakers_of("train") & speakers_of("eval")) | \
          (speakers_of("dev") & speakers_of("eval"))
if overlap:
    print("WARNING: speakers appear in multiple splits:", sorted(overlap)[:5])
else:
    print("Leakage check: no speaker appears in two splits  OK")

out_dir = os.path.join("data", "processed", "asvspoof19la")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "manifest.csv")
with open(out_path, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["path", "speaker", "attack", "label", "split"])
    w.writeheader()
    w.writerows(all_rows)

print()
print("Saved manifest :", out_path)
print("Total rows     :", len(all_rows))
print()
print("MANIFEST DONE")