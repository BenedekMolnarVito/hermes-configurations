# Hindsight memory provider — connection worked example

Session outcome: a Hindsight cloud bank (`sap-mac-hermes`) was reported as "set up but not connected." Root cause = layer 2: creds + config.json were present, but `memory.provider` was never set. One-line fix + live verification.

## State found

- `~/.hermes/.env` had `HINDSIGHT_API_KEY`, `HINDSIGHT_API_URL` (`https://api.hindsight.vectorize.io`), `HINDSIGHT_BANK_ID`. (Process `env` only showed `HINDSIGHT_BANK_ID` — the key/url were in `.env`, NOT exported. Grep `.env` directly.)
- `~/.hermes/hindsight/config.json` already had `mode: cloud`, `bank_id: sap-mac-hermes`, `recall_budget: mid`, `memory_mode: hybrid`, `auto_retain/auto_recall: true`.
- `hermes memory status` → `Provider: (none — built-in only)`  ← the actual gap.

## Fix

```bash
hermes config set memory.provider hindsight
hermes memory status   # -> Provider: hindsight, installed ✓, available ✓, active
```

## Client install (into Hermes' venv)

```bash
HPY=/Users/<user>/.hermes/hermes-agent/venv/bin/python   # from: head -5 $(command -v hermes)
"$HPY" -m pip install --upgrade 'hindsight-client>=0.4.22'
```

## Live probe pattern (write to a file, run with $HPY — NOT a heredoc)

Key points that made it a real test:
- Load creds from `~/.hermes/.env` into `os.environ` (they may not be in the process env).
- Client class is `hindsight_client.Hindsight(base_url=..., api_key=...)`. Ctor sig: `(base_url, api_key=None, timeout=300.0, user_agent=None)`.
- Cheapest authenticated round-trip: `c.get_version()` → returns `api_version='0.9.2'` + feature flags. THIS is the proof; an import is not.
- `recall` signature is positional bank-first: `recall(bank_id, query, ...)`. Calling `recall(query, bank_id=...)` raises `TypeError: missing 1 required positional argument: 'query'` — that's a PROBE BUG, not a connection failure. Don't misreport it.

## Lessons

- `hermes memory status` is the fastest way to see if any provider is active ("none — built-in only" == not activated).
- Built-in MEMORY.md/USER.md stay active alongside the external provider — it's additive, not a replacement.
- Newly-activated provider + its `hindsight_retain/recall/reflect` tools load next session, not the one that activated it.
