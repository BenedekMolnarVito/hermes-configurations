#!/usr/bin/env python3
"""Secret value sweep for Hermes config export bundles.

Byte-searches a bundle directory for live secret VALUES (not just key names or
token prefixes). NEVER prints a secret value — output is key names and
file:line locations only.

Usage:
  python secret_sweep.py --bundle <dir> --env <live .env> [--auth <live auth.json>]

Exit codes: 0 = clean, 1 = leak(s) found, 2 = usage/input error.
"""
import argparse
import json
import re
import sys
from pathlib import Path

KEY_RE = re.compile(r"(?:KEY|TOKEN|SECRET|PASS|CRED|API_KEY)")
# Plain settings that match KEY_RE but are not secret.
NOT_SECRET = re.compile(
    r"(?:_MAX_TOKENS|_MODEL|_BASE_URL|_BANK_ID|_API_URL|_TIMEOUT|_WINDOW)$"
)
PLACEHOLDER = "__SET_ME_ON_IMPORT__"
MIN_LEN = 8
SECRET_FIELD_RE = re.compile(r"(?:token|secret|key|password|credential)", re.I)


def env_secrets(path: Path):
    """Return {key: value} for secret-looking values in a .env file.
    Also inspects COMMENTED '# KEY=value' lines: live secrets hide there as
    duplicates and dodge naive ^KEY= redaction."""
    out = {}
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.lstrip("# ").strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if not key or not KEY_RE.search(key) or NOT_SECRET.search(key):
            continue
        if val == PLACEHOLDER or len(val) < MIN_LEN:
            continue
        out.setdefault(key, val)
    return out


def auth_secrets(path: Path):
    """Return {field: value} for raw token/secret strings in auth.json.
    sha256: fingerprints are non-reversible and allowed to stay."""
    out = {}

    def walk(node, name=""):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, list):
            for v in node:
                walk(v, name)
        elif isinstance(node, str):
            if (
                name
                and SECRET_FIELD_RE.search(name)
                and name != "secret_fingerprint"
                and not node.startswith("sha256:")
                and node != PLACEHOLDER
                and len(node) >= MIN_LEN
            ):
                out.setdefault(name, node)

    walk(json.loads(path.read_text(encoding="utf-8-sig")))
    return out


def scan(bundle: Path, secrets):
    """Return [(key, file, line_no)] for every byte-match; never the value."""
    hits = []
    needles = {k: v.encode("utf-8") for k, v in secrets.items()}
    for f in sorted(bundle.rglob("*")):
        if not f.is_file() or ".git" in f.parts:
            continue
        data = f.read_bytes()
        for key, needle in needles.items():
            start = 0
            while True:
                idx = data.find(needle, start)
                if idx < 0:
                    break
                line_no = data.count(b"\n", 0, idx) + 1
                hits.append((key, str(f.relative_to(bundle)), line_no))
                start = idx + 1
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--env", required=True)
    ap.add_argument("--auth")
    args = ap.parse_args()
    bundle = Path(args.bundle)
    if not bundle.is_dir():
        print(f"ERROR: bundle dir not found: {bundle}")
        return 2
    secrets = env_secrets(Path(args.env))
    if args.auth:
        secrets.update(auth_secrets(Path(args.auth)))
    if not secrets:
        print("ERROR: no secret candidates extracted from live sources")
        return 2
    print(f"candidates: {len(secrets)} secret values (names only): {', '.join(sorted(secrets))}")
    hits = scan(bundle, secrets)
    if not hits:
        print("OK: 0 live secret values found in bundle")
        return 0
    for key, rel, line_no in sorted(hits):
        print(f"LEAKED: {rel}:{line_no} ({key})")
    print(f"FAIL: {len(hits)} leak(s)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
