"""
services/threat_verifier.py — DHWANI KAVACH :: TinyFish Threat Verifier
========================================================================
Cross-references flagged caller numbers and suspicious scam trigger-keywords
against live web fraud registries using the TinyFish web-agent API.

Design principles
-----------------
* NON-BLOCKING: every public function runs the TinyFish query in a
  background daemon thread so the primary ML-inference pipeline is never
  delayed.
* NON-DESTRUCTIVE: this module is a side-channel verifier — it NEVER
  alters, replaces, or overrides any inference result from the CNN model or
  the TemporalEngine.  Its output is appended to the response as an
  optional ``tinyfish_check`` field.
* FAIL-SAFE: if the API key is absent, the network is unavailable, or the
  TinyFish call raises any exception, the verifier logs a warning and
  returns a graceful stub — the rest of the system continues unaffected.

Usage (non-blocking, from any Flask route)
------------------------------------------
    from services.threat_verifier import verify_async, get_result

    # Kick off background check; returns a unique job_id immediately.
    job_id = verify_async(caller_number="9876543210",
                          keywords=["otp", "bank freeze", "officer"])

    # … do primary ML inference here …

    # Retrieve result (None if still running; dict once done).
    tf_result = get_result(job_id)

Or use the synchronous helper (blocks, only for tests / CLI):
    from services.threat_verifier import verify_sync
    print(verify_sync(caller_number="9876543210"))
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from typing import Dict, List, Optional

# ── Optional dependency guard ─────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)   # Populate os.environ from .env if present
    _DOTENV_OK = True
except ImportError:
    _DOTENV_OK = False
    logging.getLogger(__name__).warning(
        "python-dotenv not installed; .env file will NOT be loaded. "
        "Set TINYFISH_API_KEY in the system environment manually."
    )

try:
    from tinyfish import TinyFish
    _TINYFISH_AVAILABLE = True
except ImportError:
    _TINYFISH_AVAILABLE = False
    logging.getLogger(__name__).warning(
        "tinyfish package not installed. "
        "Run: pip install tinyfish  — TinyFish checks will be skipped."
    )

# ── Module-level logger ───────────────────────────────────────────────────────
log = logging.getLogger(__name__)

# ── In-memory result store (lightweight; resets on server restart) ────────────
_results: Dict[str, Optional[dict]] = {}   # job_id -> result or None (pending)
_lock = threading.Lock()

# ── Fraud-registry URLs to query ─────────────────────────────────────────────
_FRAUD_REGISTRIES = [
    "https://cybercrime.gov.in",
    "https://sancharsaathi.gov.in",
]

# ── Scam-keyword context for the search query ────────────────────────────────
_SCAM_KEYWORDS_CONTEXT = (
    "phone scam fraud impersonation OTP UPI bank freeze digital arrest "
    "voice clone deepfake India cybercrime"
)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_query(caller_number: str, keywords: List[str]) -> str:
    """Build the natural-language query sent to the TinyFish agent."""
    parts = []
    if caller_number:
        parts.append(f"Is phone number {caller_number} listed in any scam or fraud registry?")
    if keywords:
        kw_str = ", ".join(f'"{k}"' for k in keywords[:10])
        parts.append(
            f"Are any of these phrases commonly associated with phone scams: {kw_str}?"
        )
    parts.append(
        "Check cybercrime.gov.in, sancharsaathi.gov.in, and any public fraud-number database. "
        "Return: is_flagged (true/false), confidence (low/medium/high), and a short summary."
    )
    return "  ".join(parts)


def _run_tinyfish_query(job_id: str, caller_number: str, keywords: List[str]) -> None:
    """Background thread target — runs TinyFish query and stores result."""
    started_at = time.time()
    result: dict = {
        "job_id": job_id,
        "caller_number": caller_number,
        "keywords_checked": keywords,
        "is_flagged": None,
        "confidence": "unknown",
        "summary": "",
        "source": "tinyfish",
        "elapsed_s": None,
        "error": None,
    }

    api_key = os.getenv("TINYFISH_API_KEY", "").strip()
    if not api_key:
        result["error"] = "TINYFISH_API_KEY not set — skipping web verification"
        result["summary"] = "No API key configured; web fraud registry check skipped."
        log.warning("[ThreatVerifier] %s", result["error"])
        _store(job_id, result)
        return

    if not _TINYFISH_AVAILABLE:
        result["error"] = "tinyfish package not installed"
        result["summary"] = "TinyFish package unavailable; install with: pip install tinyfish"
        _store(job_id, result)
        return

    try:
        client = TinyFish(api_key=api_key)
        query = _build_query(caller_number, keywords)
        log.info("[ThreatVerifier] job=%s | querying TinyFish: %s", job_id, query[:120])

        # Use the search API first (fast); fall back to agent.run for deeper check.
        try:
            search_resp = client.search.query(query=query)
            raw_text = str(search_resp)
        except Exception as search_err:
            log.warning("[ThreatVerifier] search.query failed (%s); trying agent.run", search_err)
            agent_resp = client.agent.run(
                goal=query,
                url=_FRAUD_REGISTRIES[0],
            )
            raw_text = str(agent_resp.result) if hasattr(agent_resp, "result") else str(agent_resp)

        # Heuristic parse — look for clear indicators in the free-text response.
        low = raw_text.lower()
        if any(w in low for w in ("flagged", "scam", "fraud", "reported", "blacklisted")):
            result["is_flagged"] = True
            result["confidence"] = "medium"
        elif any(w in low for w in ("not found", "no result", "not listed", "clean")):
            result["is_flagged"] = False
            result["confidence"] = "low"
        else:
            result["is_flagged"] = None
            result["confidence"] = "low"

        # Truncate summary to keep response payload lean.
        result["summary"] = raw_text[:600].strip()
        log.info("[ThreatVerifier] job=%s done | flagged=%s", job_id, result["is_flagged"])

    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["summary"] = "TinyFish query encountered an error; primary verdict unaffected."
        log.exception("[ThreatVerifier] job=%s error: %s", job_id, exc)

    finally:
        result["elapsed_s"] = round(time.time() - started_at, 2)
        _store(job_id, result)


def _store(job_id: str, result: dict) -> None:
    with _lock:
        _results[job_id] = result


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def verify_async(
    caller_number: str = "",
    keywords: Optional[List[str]] = None,
) -> str:
    """
    Start a background TinyFish verification and return a job_id immediately.

    Parameters
    ----------
    caller_number : str
        The phone number that was flagged by the primary pipeline.
    keywords : list[str], optional
        Scam trigger-phrases detected in the call (e.g. ["otp", "bank freeze"]).

    Returns
    -------
    str
        A UUID job-id.  Poll with :func:`get_result` to retrieve the outcome.
    """
    job_id = str(uuid.uuid4())
    kw = keywords or []
    with _lock:
        _results[job_id] = None   # Mark as pending

    t = threading.Thread(
        target=_run_tinyfish_query,
        args=(job_id, caller_number, kw),
        daemon=True,
        name=f"TFVerifier-{job_id[:8]}",
    )
    t.start()
    log.info("[ThreatVerifier] started async job=%s for number=%s", job_id, caller_number or "(none)")
    return job_id


def get_result(job_id: str) -> Optional[dict]:
    """
    Return the verification result for *job_id*, or ``None`` if still pending.

    Parameters
    ----------
    job_id : str
        The value returned by :func:`verify_async`.

    Returns
    -------
    dict | None
        Result dict when the background thread has finished, else ``None``.
    """
    with _lock:
        return _results.get(job_id)


def verify_sync(
    caller_number: str = "",
    keywords: Optional[List[str]] = None,
    timeout_s: float = 30.0,
) -> dict:
    """
    Synchronous convenience wrapper — blocks until the result is ready.
    Intended for tests and CLI usage; do NOT call from Flask request handlers.

    Parameters
    ----------
    caller_number : str
        Phone number to check.
    keywords : list[str], optional
        Scam trigger-phrases.
    timeout_s : float
        Maximum seconds to wait before returning a timeout stub.

    Returns
    -------
    dict
        Verification result.
    """
    job_id = verify_async(caller_number=caller_number, keywords=keywords)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        result = get_result(job_id)
        if result is not None:
            return result
        time.sleep(0.2)
    return {
        "job_id": job_id,
        "error": f"timeout after {timeout_s}s",
        "is_flagged": None,
        "confidence": "unknown",
        "summary": "TinyFish check timed out; primary verdict unaffected.",
        "source": "tinyfish",
    }
