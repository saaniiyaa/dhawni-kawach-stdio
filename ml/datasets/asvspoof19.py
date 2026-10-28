# ml/datasets/asvspoof19.py
# Reads the OFFICIAL ASVspoof 2019 LA protocol files and builds our manifest rows.

import os

# where the dataset lives on THIS laptop
LA_ROOT = r"C:\dhwani_data\LA\LA"

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


def check_layout(root=LA_ROOT):
    """Friendly check: does the folder look like extracted ASVspoof 2019 LA?"""
    problems = []
    if not os.path.isdir(root):
        problems.append(f"Cannot find the dataset folder: {root}")
    for split, rel in list(PROTOCOLS.items()) + list(FLAC_DIRS.items()):
        path = os.path.join(root, rel)
        if not os.path.isdir(os.path.dirname(path)) and not os.path.isdir(path):
            problems.append(f"Missing: {path}")
    return problems


def parse_protocol(root, split):
    """Read one protocol file -> list of row dictionaries.
    Tolerant format: SPEAKER  UTTERANCE  ATTACK(-)  [possible extra cols]  LABEL
    We only trust the first two fields and the LAST field (bonafide/spoof)."""
    path = os.path.join(root, PROTOCOLS[split])
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parts = line.split()
            if len(parts) < 4:
                continue
            label = parts[-1]
            if label not in ("bonafide", "spoof"):
                continue
            speaker, utt = parts[0], parts[1]
            # attack code position varies between dataset releases:
            # take the first non "-" token between the utterance and the label
            attack = "none"
            for p in parts[2:-1]:
                if p != "-":
                    attack = p
                    break
            audio = os.path.join(root, FLAC_DIRS[split], utt + ".flac")
            rows.append({
                "path": audio,
                "speaker": speaker,
                "attack": attack,
                "label": label,           # 'bonafide' (real) or 'spoof' (fake)
                "split": split,
            })
    return rows