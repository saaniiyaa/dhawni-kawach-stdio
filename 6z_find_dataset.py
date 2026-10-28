# 6z_find_dataset.py
# DETECTIVE: finds where ASVspoof was actually extracted on this laptop
# (or proves it was never extracted at all). Safe, read-only, fast.

import os

HOME = os.path.expanduser("~")     # -> C:\Users\saniyaa
CANDIDATE_ROOTS = [
    r"C:\dhwani_data",
    os.path.join(HOME, "Downloads"),
    os.path.join(HOME, "OneDrive", "Desktop"),
    os.path.join(HOME, "Desktop"),
    os.path.join(HOME, "OneDrive", "Documents"),
    os.path.join(HOME, "Documents"),
    r"C:\dhwani_data\LA.zip",      # in case a FOLDER with this odd name exists
]

TARGET = "ASVspoof2019_LA_train"   # the folder that must exist somewhere after extraction


def describe(path):
    if os.path.isdir(path):
        print(f"  [FOLDER] {path}")
    elif os.path.exists(path):
        try:
            gb = os.path.getsize(path) / 1e9
        except OSError:
            gb = 0
        print(f"  [zipfile] {path}   ({gb:.2f} GB)")
    else:
        print(f"  [nothing] {path}")


print("=" * 60)
print("STEP 1 - what's in the likely places?")
print("=" * 60)
for root in CANDIDATE_ROOTS:
    if not os.path.isdir(root):
        continue
    print(f"\nLooking inside: {root}")
    try:
        entries = sorted(os.listdir(root))
    except OSError as err:
        print("   cannot read:", err)
        continue
    interesting = [e for e in entries
                   if "la" in e.lower() or "asvspoof" in e.lower() or "dhwani" in e.lower()]
    if interesting:
        for e in interesting:
            describe(os.path.join(root, e))
    else:
        print("   (no LA / ASVspoof / dhwani items here)")

print()
print("=" * 60)
print(f"STEP 2 - deep search for a folder named '{TARGET}'")
print("=" * 60)
found = []
for base in CANDIDATE_ROOTS:
    base = os.path.abspath(base)
    if not os.path.isdir(base):
        continue
    for dirpath, dirnames, filenames in os.walk(base):
        depth = dirpath[len(base):].count(os.sep)
        if depth >= 4:                     # don't dig forever
            dirnames[:] = []
            continue
        if TARGET in dirnames:
            parent = os.path.dirname(os.path.join(dirpath, TARGET))
            if parent not in found:
                found.append(parent)
                print("  FOUND:", parent)

print()
print("=" * 60)
print("VERDICT")
print("=" * 60)
if found:
    print("The dataset IS extracted. In ml/datasets/asvspoof19.py set:")
    print(f'    LA_ROOT = r"{found[0]}"')
    print("Then run 6_build_manifest.py again.")
else:
    print("NOT extracted yet. You were browsing INSIDE the zip (Windows allows")
    print("that without extracting - that's why the path looked real).")
    print()
    print("DO THIS NOW:")
    print(" 1. File Explorer -> C:\\dhwani_data (or Downloads, wherever LA.zip is)")
    print(" 2. Right-click the LA.zip FILE (icon with a zipper on it)")
    print(" 3. Choose 'Extract All...'")
    print(" 4. Destination box: make it exactly  C:\\dhwani_data   (delete anything")
    print("    extra like 'LA.zip' at the end)  -> click Extract")
    print(" 5. Wait 10-25 minutes (progress window must FINISH)")
    print(" 6. You should now have C:\\dhwani_data\\LA\\ with 4 folders inside")
    print(" 7. Run this detective script again to confirm")