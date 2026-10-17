"""
jevlib/envload.py — load <home>/.env (optional; key normally comes from user env) into os.environ for hook subprocesses.

Hooks are spawned as bare subprocesses. Depending on the invocation path
(depending on launcher), TYPESAFE_API_KEY may NOT be
present in the subprocess environment even though it lives in <home>/.env.
A hook calls `envload.ensure()` ONCE at startup to populate os.environ from the
.env file for any keys not already set. jevlib itself stays pure (reads only
os.environ), so the test suite — which never calls ensure() — is unaffected.

Never raises. Never logs or returns secret values. Only sets keys that are
absent from os.environ (an explicitly-set env var always wins).
"""
import os

from . import config


def ensure() -> None:
    """Populate os.environ from <home>/.env for absent keys. Best-effort."""
    try:
        env_path = config.home() / ".env"
        if not env_path.exists():
            return
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key and key not in os.environ:
                os.environ[key] = val.strip().strip('"').strip("'")
    except Exception:
        pass  # a hook must never fail because .env could not be read
