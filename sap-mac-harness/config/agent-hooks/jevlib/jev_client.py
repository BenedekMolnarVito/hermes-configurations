"""
jevlib/jev_client.py — JEV HTTP client with fail-open semantics.

stdlib only: json, os, time, urllib.request, urllib.error
Python 3.9 compatible.

Public API
----------
UNAVAILABLE        module-level sentinel object
JevError           exception for all jev errors
noul()             question builder
choice()           question builder
score()            question builder
log_event()        append one JSON line to logs/jev-guard.jsonl (never raises)
call_jev()         POST to /v1/systemone; 429/529 retry with backoff; raises JevError
safe_decide()      call_jev wrapper that catches all errors and returns UNAVAILABLE
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from . import config

# ---------------------------------------------------------------------------
# Sentinel & exception
# ---------------------------------------------------------------------------

UNAVAILABLE = object()


class JevError(Exception):
    pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _base_url() -> str:
    return os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai").rstrip("/")


# ---------------------------------------------------------------------------
# Question builders
# ---------------------------------------------------------------------------

def noul(instructions: str, criteria=None) -> dict:
    q: dict = {"type": "noul", "instructions": instructions}
    if criteria is not None:
        q["criteria"] = criteria
    return q


def choice(instructions: str, criteria: str) -> dict:
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def score(instructions: str, criteria: str) -> dict:
    return {"type": "score", "instructions": instructions, "criteria": criteria}


# ---------------------------------------------------------------------------
# log_event
# ---------------------------------------------------------------------------

def log_event(reason: str, **fields) -> None:
    """Append one JSON line to config.home()/logs/jev-guard.jsonl. Never raises."""
    try:
        log_dir = config.home() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        entry = {"ts": time.time(), "reason": reason}
        for k, v in fields.items():
            if k != "api_key":
                entry[k] = v
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with open(log_dir / "jev-guard.jsonl", "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:  # noqa: BLE001 — intentional blanket catch
        pass


# ---------------------------------------------------------------------------
# call_jev
# ---------------------------------------------------------------------------

def call_jev(state, questions, *, timeout=None) -> dict:
    """
    POST {state, model, questions} to /v1/systemone.

    Retries on 429/529 (up to 3 attempts, exponential backoff 2**attempt seconds).
    Raises JevError for all error conditions.
    Returns the answers dict on success.
    """
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not key:
        raise JevError("no_api_key")

    cfg = config.load_config()
    model = cfg["jev"]["model"]
    if timeout is None:
        timeout = cfg["jev"]["timeout_seconds"]

    payload = json.dumps({"state": state, "model": model, "questions": questions}).encode("utf-8")
    url = _base_url() + "/v1/systemone"
    headers = {
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
    }

    last_error: Exception | None = None
    for attempt in range(3):
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            code = exc.code
            if code in (429, 529):
                last_error = exc
                time.sleep(2 ** attempt)
                continue
            raise JevError("http_%d" % code) from exc
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise JevError("transport_" + type(exc).__name__) from exc

        # Successful HTTP response
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            raise JevError("transport_" + type(exc).__name__) from exc

        answers = data.get("answers")
        if not isinstance(answers, dict):
            raise JevError("malformed_response")
        return answers

    # All retries exhausted on 429/529
    raise JevError("http_%d" % last_error.code) from last_error


# ---------------------------------------------------------------------------
# safe_decide
# ---------------------------------------------------------------------------

def safe_decide(state, questions, *, timeout=None):
    """
    Wraps call_jev with complete fail-open semantics.
    On JevError or any other exception: log and return UNAVAILABLE.
    Never raises.
    """
    try:
        return call_jev(state, questions, timeout=timeout)
    except JevError as exc:
        log_event("jev_unavailable", detail=str(exc))
        return UNAVAILABLE
    except Exception as exc:  # noqa: BLE001
        log_event("jev_unexpected", detail=type(exc).__name__)
        return UNAVAILABLE
