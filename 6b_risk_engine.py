# 6b_risk_engine.py
# Demos the risk engine with FAKE score streams (later: real detector feeds it).

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import random
from ml.engine.temporal import TemporalEngine, policy_for

random.seed(42)

BARS = {"SAFE": "[      OK ]", "SUSPICIOUS": "[ WARN  ]",
        "HIGH_RISK": "[ HOLD! ]", "INSUFFICIENT_AUDIO": "[ listen ]"}


def run_call(title, scores, voiced=0.9):
    print("=" * 66)
    print("CALL:", title)
    print("=" * 66)
    eng = TemporalEngine()
    last = None
    for i, p in enumerate(scores, start=1):
        r = eng.update(p, voiced)
        last = r
        print(f"  window {i:2d}  raw score {p:.2f}   call evidence {r['call_p']:.2f}"
              f"   {r['tier']:<18s} {BARS[r['tier']]}")
    pol = policy_for(last["tier"])
    print(f"  --> FINAL: {last['tier']}")
    print(f"      ACTION : {pol['action']}")
    print(f"      SCREEN : {pol['ui']}")
    if pol["step_up"]:
        print(f"      STEP-UP: {pol['step_up']}")
    print(f"      Money transfer allowed: {pol['allow_sensitive_action']}")
    print()


# ---- the four fake calls (THESE were the missing lines) ----
honest = [max(0.02, min(0.45, random.gauss(0.12, 0.08))) for _ in range(12)]
sneaky = [max(0.30, min(0.80, random.gauss(0.55, 0.10))) for _ in range(14)]
blatant = [min(0.98, max(0.75, random.gauss(0.90, 0.06))) for _ in range(12)]
glitch = [max(0.02, min(0.35, random.gauss(0.10, 0.07))) for _ in range(12)]
glitch[6] = 0.99   # detector panics for ONE window

run_call("honest caller (scores hover low)", honest)
run_call("sneaky clone (scores hover in the middle)", sneaky)
run_call("blatant clone (scores stay high)", blatant)
run_call("honest call + ONE detector glitch at window 7", glitch)

print("ENGINE DEMO DONE")