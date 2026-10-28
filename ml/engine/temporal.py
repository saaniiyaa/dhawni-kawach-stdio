# ml/engine/temporal.py
# Converts noisy per-window detector scores into ONE call-level decision.
# This is what makes us a product, not just a classifier.
# Four protections built in:
#   1. refuses to judge before enough speech (INSUFFICIENT_AUDIO)
#   2. evidence accumulates over the whole call (log-odds meter)
#   3. one crazy window cannot dominate (clipping + dwell time)
#   4. harder to LEAVE high risk than enter it (safety-first hysteresis)

from dataclasses import dataclass, field
import math

SAFE, SUSPICIOUS, HIGH_RISK, INSUFFICIENT = "SAFE", "SUSPICIOUS", "HIGH_RISK", "INSUFFICIENT_AUDIO"


@dataclass
class EngineConfig:
    theta_lo: float = 0.78         # suspicious threshold
    theta_hi: float = 0.90         # high-risk threshold
    theta_neutral: float = 0.70    # calibrated decision boundary for neutral evidence
    ema_alpha: float = 0.35        # smoothing for the number shown on screen
    min_voiced_seconds: float = 2.0   # refuse to judge before this much speech
    dwell_windows: int = 2         # consecutive agreeing windows needed to change tier
    llr_clip: float = 3.5          # one window can add at most this much evidence
    llr_decay: float = 0.95        # old evidence slowly forgotten


@dataclass
class EngineState:
    ema: float = 0.0
    llr: float = -1.5              # default to safe baseline
    n_windows: int = 0
    voiced_seconds: float = 0.0
    tier: str = INSUFFICIENT
    _pending: str = INSUFFICIENT
    _pending_count: int = 0
    history: list = field(default_factory=list)


class TemporalEngine:
    def __init__(self, cfg=None):
        self.cfg = cfg or EngineConfig()
        self.s = EngineState()

    def reset(self):
        self.s = EngineState()

    @staticmethod
    def _llr(p, theta_ref=0.5, eps=1e-6):
        p = min(max(p, eps), 1 - eps)
        theta_ref = min(max(theta_ref, eps), 1 - eps)
        # Log-odds ratio relative to calibrated decision threshold
        return math.log(p / (1 - p)) - math.log(theta_ref / (1 - theta_ref))

    def update(self, p_spoof, voiced_seconds, t=None):
        c, s = self.cfg, self.s
        s.n_windows += 1
        s.voiced_seconds += voiced_seconds
        s.ema = p_spoof if s.n_windows == 1 else c.ema_alpha * p_spoof + (1 - c.ema_alpha) * s.ema
        
        # If window is mostly silent/unvoiced (<0.6s), do not accumulate fake evidence
        if voiced_seconds >= 0.6:
            step = max(-c.llr_clip, min(c.llr_clip, self._llr(p_spoof, c.theta_neutral)))
            s.llr = s.llr * c.llr_decay + step * min(voiced_seconds, 1.0)  # evidence meter
        else:
            # Gentle decay towards safe baseline during pauses
            s.llr = s.llr * c.llr_decay - 0.15

        call_p = 1 / (1 + math.exp(-s.llr))

        if s.voiced_seconds < c.min_voiced_seconds:
            target = INSUFFICIENT
        elif s.tier == HIGH_RISK:      # hysteresis: easier to stay in high risk
            target = HIGH_RISK if call_p >= c.theta_lo else (
                SUSPICIOUS if call_p >= c.theta_lo * 0.6 else SAFE)
        elif call_p >= c.theta_hi:
            target = HIGH_RISK
        elif call_p >= c.theta_lo:
            target = SUSPICIOUS
        else:
            target = SAFE

        if target == s._pending:
            s._pending_count += 1
        else:
            s._pending, s._pending_count = target, 1
        if s._pending_count >= (1 if target == INSUFFICIENT else self.cfg.dwell_windows):
            s.tier = target

        out = {"t": t, "window_p": float(p_spoof), "ema": float(s.ema),
               "call_p": float(call_p), "llr": float(s.llr), "tier": s.tier,
               "voiced_seconds": round(s.voiced_seconds, 2), "n_windows": s.n_windows}
        s.history.append(out)
        return out


# ---------------- the prevention policy: what the bank/app actually does ----------------
PREVENTION = {
    INSUFFICIENT: dict(action="OBSERVE", ui="Listening... not enough speech to judge yet",
                       allow_sensitive_action=True, step_up=None),
    SAFE:         dict(action="ALLOW", ui="No synthetic-speech indicators detected",
                       allow_sensitive_action=True, step_up=None),
    SUSPICIOUS:   dict(action="WARN", ui="Possible synthetic speech - verify before acting",
                       allow_sensitive_action=True,
                       step_up="Ask a pre-agreed code word OR call back on the saved number"),
    HIGH_RISK:    dict(action="HOLD", ui="High risk of cloned voice - sensitive action paused",
                       allow_sensitive_action=False,
                       step_up="Out-of-band callback to registered number + second approver"),
}


def policy_for(tier):
    return PREVENTION[tier]