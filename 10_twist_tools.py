# 10_twist_tools.py
# Tests both signature features:
#   PART 1 - Scam-Script Radar on real-world style scam lines vs innocent lines
#   PART 2 - Family Voiceprint: enrol team members, then cross-verify everyone
# Needs: data/team/*.wav recordings (from 5_record_team.py).

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import glob

from ml.audio.io import load
from ml.engine.scam_radar import scan
from ml.engine.voiceprint_falak import enrol, verify, enrolled_names

print("=" * 70)
print("PART 1 - SCAM-SCRIPT RADAR")
print("=" * 70)

test_lines = [
    ("SCAM?  ", "Sir this is CBI, a digital arrest warrant is issued in your name, "
                "transfer immediately to close the case."),
    ("SCAM?  ", "Papa accident ho gaya hai, hospital me hain, paise turant bhejo "
                "aur OTP bhi bata do."),
    ("SCAM?  ", "Your KYC will expire today, share the OTP to verify your account "
                "right now."),
    ("NORMAL ", "Beta, dinner par aaja, gajar halwa banaya hai."),
    ("NORMAL ", "Hi, this is your college library - your book is due next week."),
    ("BORDER ", "The bank manager wants to talk to you about your account."),
]

for tag, line in test_lines:
    r = scan(line)
    print(f"{tag} score {r['score']:3d} [{r['level']:6s}] cats={r['categories']}")
    print(f"        line: {line[:74]}")

print()
print("=" * 70)
print("PART 2 - FAMILY VOICEPRINT  (enrol + cross-verify)")
print("=" * 70)

team_files = sorted(glob.glob("data/team/*.wav"))
if len(team_files) < 2:
    print(f"Need at least 2 files in data/team/ (found {len(team_files)}).")
    print("Run 5_record_team.py with your team, then run this again.")
else:
    names = []
    for f in team_files:
        name = os.path.splitext(os.path.basename(f))[0]
        y = load(f)
        if len(y) < 2 * 16000:
            print(f"skipping {name} (recording under 2 s)")
            continue
        enrol(name, [y])
        names.append(name)
        print(f"enrolled: {name}")

    print()
    print("Cross-verify table (rows = who is speaking, cols = who they CLAIM to be):")
    print()
    header = f"{'speaking \\ claims':22s}" + "".join(f"{n[:12]:>14s}" for n in names)
    print(header)
    for f, speaker in zip(team_files, names):
        y = load(f)
        row = f"{speaker[:22]:22s}"
        for claimed in names:
            v = verify(claimed, y)
            mark = "?" if "error" in v else (
                "MATCH" if v["verdict"].startswith("MATCH") else "other")
            row += f"{mark:>14s}"
        print(row)

    print()
    print("Detailed check - each speaker verified as themselves:")
    for f, speaker in zip(team_files, names):
        v = verify(speaker, load(f))
        if "error" in v:
            print(speaker, "->", v["error"])
        else:
            print(f"  {speaker[:18]:18s} sim={v['sim_claimed']:.3f} "
                  f"vs best other ({v['best_other']}) {v['sim_other']:.3f} "
                  f"margin={v['margin']:+.3f} -> {v['verdict']}")

    print()
    print(f"enrolled prints stored in: data/voiceprints/  ({len(enrolled_names())} people)")
    print("These files stay on this machine only - never push them to git.")

print()
print("TWIST TOOLS DONE")