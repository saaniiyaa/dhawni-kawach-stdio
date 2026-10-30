"""
services/armoriq_guard.py — ArmorIQ Intent Assurance & Agent Runtime Governance
================================================================================
Cryptographically verifies defensive circuit-breaker actions before execution in
Dhwani Kavach Studio (emergency call drop, Flash v2.5 voice alert, telecom PIN challenge).

Core Responsibilities:
1. Policy Verification:
   - Enforces risk_score >= 0.75 threshold required for high-impact defensive
     circuit-breaker actions (e.g. TERMINATE_CALL, VOICE_INTERCEPT_ALERT, PIN_CHALLENGE).
   - Rejects unverified or below-threshold autonomous actions with structured audit reasons.
2. Cryptographic Intent Receipt Signing:
   - Computes canonical SHA-256 intent digests and HMAC-SHA256 audit tokens.
   - Generates unique ArmorIQ intent tokens formatted as AIQ-<12_HEX_UPPER>.
   - Provides verifiable audit trails for cyber-crime forensic dossiers (I4C 1930 compliance).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

logger = logging.getLogger("armoriq_guard")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# ── Configurable Policy Constraints ───────────────────────────────────────────
DEFAULT_CIRCUIT_BREAKER_THRESHOLD: float = 0.75
POLICY_VERSION: str = "ArmorIQ-Runtime-Governance-v2.1"
ARMORIQ_SECRET_KEY: str = os.getenv("ARMORIQ_SECRET_KEY", "armoriq_dhwani_kavach_circuit_breaker_key_2026")

# Recognized high-impact defensive actions governed by circuit-breaker policies
DEFENSIVE_CIRCUIT_BREAKER_ACTIONS: Set[str] = {
    "TERMINATE_CALL",
    "VOICE_INTERCEPT_ALERT",
    "PIN_CHALLENGE",
    "TELECOM_PIN_CHALLENGE",
    "EMERGENCY_CALL_DROP",
    "CALL_HOLD",
    "CIRCUIT_BREAKER_TRIGGER",
}


class ArmorIQGuard:
    """
    ArmorIQ Intent Assurance Runtime Guard.
    Validates intent authorization against governance policies and issues
    cryptographically signed SHA-256 intent receipts.
    """

    def __init__(
        self,
        default_threshold: float = DEFAULT_CIRCUIT_BREAKER_THRESHOLD,
        secret_key: str = ARMORIQ_SECRET_KEY,
    ):
        self.default_threshold = float(default_threshold)
        self.secret_key = secret_key.encode("utf-8")
        self._audit_log: Dict[str, Dict[str, Any]] = {}

    def _canonical_representation(
        self,
        action: str,
        risk_score: float,
        context: Optional[Dict[str, Any]],
        timestamp: str,
        nonce: str,
    ) -> bytes:
        """
        Builds a deterministic JSON byte payload for cryptographic digest computation.
        """
        canonical_dict = {
            "action": action.strip().upper(),
            "context": context or {},
            "nonce": nonce,
            "policy_version": POLICY_VERSION,
            "risk_score": round(float(risk_score), 4),
            "timestamp": timestamp,
        }
        return json.dumps(canonical_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sign_intent_receipt(
        self,
        action: str,
        risk_score: float,
        context: Optional[Dict[str, Any]] = None,
        authorized: bool = True,
        threshold: float = DEFAULT_CIRCUIT_BREAKER_THRESHOLD,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generates a cryptographically signed SHA-256 intent receipt and assigns an AIQ-* Intent ID.
        """
        action_clean = action.strip().upper()
        now_utc = datetime.now(timezone.utc).isoformat()
        raw_nonce = hashlib.sha256(f"{action_clean}:{time.time_ns()}".encode("utf-8")).hexdigest()[:16]

        canonical_bytes = self._canonical_representation(
            action=action_clean,
            risk_score=risk_score,
            context=context,
            timestamp=now_utc,
            nonce=raw_nonce,
        )

        canonical_digest = hashlib.sha256(canonical_bytes).hexdigest()
        hmac_sig = hmac.new(self.secret_key, canonical_bytes, hashlib.sha256).hexdigest()

        # Format standardized ArmorIQ Intent ID: AIQ-<10-char uppercase hex signature>
        intent_id = f"AIQ-{hmac_sig[:10].upper()}"

        receipt = {
            "intent_id": intent_id,
            "action": action_clean,
            "authorized": authorized,
            "status": "AUTHORIZED" if authorized else "POLICY_REJECTED",
            "risk_score": float(risk_score),
            "threshold": float(threshold),
            "policy": POLICY_VERSION,
            "timestamp": now_utc,
            "canonical_digest": canonical_digest,
            "signature": hmac_sig,
            "nonce": raw_nonce,
            "reason": reason or ("Action authorized under ArmorIQ policy" if authorized else "Action rejected by policy"),
            "audit_token": f"armoriq_sig_{hmac_sig[:24]}",
        }

        # Store in local in-memory audit ledger
        self._audit_log[intent_id] = receipt
        return receipt

    def verify_action_intent(
        self,
        action: str = "VOICE_INTERCEPT_ALERT",
        risk_score: float = 0.94,
        context: Optional[Dict[str, Any]] = None,
        threshold: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Verifies whether a defensive action is authorized by ArmorIQ Intent Assurance.
        
        Rule:
        Defensive circuit-breaker actions require risk_score >= threshold (default 0.75).
        """
        action_clean = (action or "VOICE_INTERCEPT_ALERT").strip().upper()
        eff_threshold = float(threshold if threshold is not None else self.default_threshold)
        score = float(risk_score)

        is_defensive = (
            action_clean in DEFENSIVE_CIRCUIT_BREAKER_ACTIONS
            or kwargs.get("is_circuit_breaker", False)
            or "ALERT" in action_clean
            or "TERMINATE" in action_clean
            or "CHALLENGE" in action_clean
        )

        if is_defensive:
            if score >= eff_threshold:
                authorized = True
                status_reason = (
                    f"Defensive circuit-breaker action '{action_clean}' authorized: "
                    f"risk score {score:.2f} satisfies required policy threshold {eff_threshold:.2f}."
                )
            else:
                authorized = False
                status_reason = (
                    f"Defensive circuit-breaker action '{action_clean}' REJECTED: "
                    f"risk score {score:.2f} is below mandatory policy threshold {eff_threshold:.2f}."
                )
        else:
            # Non-circuit-breaker / informational actions
            authorized = True
            status_reason = f"Action '{action_clean}' authorized under standard policy."

        receipt = self.sign_intent_receipt(
            action=action_clean,
            risk_score=score,
            context=context,
            authorized=authorized,
            threshold=eff_threshold,
            reason=status_reason,
        )

        if authorized:
            logger.info(
                "[ARMORIQ GUARDIAN] Action '%s' authorized under Intent ID: %s (Score: %.2f >= %.2f)",
                action_clean,
                receipt["intent_id"],
                score,
                eff_threshold,
            )
        else:
            logger.warning(
                "[ARMORIQ GUARDIAN] Action '%s' BLOCKED under Intent ID: %s (Score: %.2f < %.2f)",
                action_clean,
                receipt["intent_id"],
                score,
                eff_threshold,
            )

        return receipt

    def verify_receipt_signature(self, receipt: Dict[str, Any]) -> bool:
        """
        Validates the cryptographic authenticity and integrity of a signed intent receipt.
        """
        try:
            action = receipt["action"]
            risk_score = receipt["risk_score"]
            context = receipt.get("context", {})
            timestamp = receipt["timestamp"]
            nonce = receipt["nonce"]
            expected_sig = receipt["signature"]

            canonical_bytes = self._canonical_representation(
                action=action,
                risk_score=risk_score,
                context=context,
                timestamp=timestamp,
                nonce=nonce,
            )
            recomputed = hmac.new(self.secret_key, canonical_bytes, hashlib.sha256).hexdigest()
            return hmac.compare_digest(recomputed, expected_sig)
        except Exception as err:
            logger.error("ArmorIQ receipt signature verification failed: %s", err)
            return False

    def get_intent_receipt(self, intent_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a previously issued intent receipt from the audit ledger."""
        return self._audit_log.get(intent_id)


# Global Singleton Instance & module exports
armoriq_guard = ArmorIQGuard()
armoriq = armoriq_guard


def verify_action_intent(
    action: str = "VOICE_INTERCEPT_ALERT",
    risk_score: float = 0.94,
    context: Optional[Dict[str, Any]] = None,
    threshold: Optional[float] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Module-level convenience wrapper for armoriq_guard.verify_action_intent."""
    return armoriq_guard.verify_action_intent(
        action=action, risk_score=risk_score, context=context, threshold=threshold, **kwargs
    )

