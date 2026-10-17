---
name: hermes-external-integrations
description: "Connect/fix Hermes external integrations (memory, MCP)."
version: 1.0.0
metadata:
  hermes:
    tags: [hermes, memory-provider, mcp, integration, troubleshooting, activation, verification]
---

# Hermes External Integrations

Connecting and troubleshooting external services wired into a Hermes instance — memory providers (Hindsight, Honcho, Mem0, OpenViking, Supermemory, ...), MCP servers, and similar plugins. Governs the class of task: "a bank/server/provider exists and creds are supposedly set, but Hermes isn't using it."

The bundled `hermes-agent` skill is the authoritative reference for config keys and CLI syntax — load it too. This skill captures the DIAGNOSTIC + VERIFICATION discipline that the reference docs don't emphasize.

## Core principle: "configured" != "active" != "working"

Three independent layers, checked separately. A user reporting "it's set up but not connected" almost always has one layer done and another missing:

1. **Credentials present** — API key / URL / IDs in `~/.hermes/.env` (secrets) and behavioral config in the provider's config file (e.g. `~/.hermes/hindsight/config.json`, `honcho.json`, `mem0.json`). NEVER put non-secret settings in `.env`.
2. **Provider ACTIVATED** — the switch that tells Hermes to use it. For memory: `memory.provider` in `config.yaml`. This is the step most often missing when everything else looks right.
3. **Connection WORKS** — creds authenticate and the remote actually responds. Config looking right proves nothing.

## Diagnostic sequence (memory provider example)

```bash
# Layer 2: is a provider actually active?
hermes memory status          # "Provider: (none — built-in only)" == NOT activated

# Layer 1: what creds/config already exist? (env vars, .env, provider config.json)
env | grep -iE '<provider>'                       # process env
grep -iE '<provider>' ~/.hermes/.env              # the real secret store — check here even if process env is empty
cat ~/.hermes/<provider>/config.json              # behavioral config
```

Pitfall: the user may say "the key is in an env var" when it's actually only in `~/.hermes/.env` (loaded by Hermes, not exported to your shell). Always grep `~/.hermes/.env` before concluding a credential is missing. Don't stall asking the user for a key that's already on disk.

## Activating

Use the CLI setter, never hand-edit `config.yaml` (a stray indent corrupts it and breaks the live gateway):

```bash
hermes config set memory.provider <name>    # e.g. hindsight
hermes memory status                        # confirm: Provider: <name>, installed ✓, available ✓
```

Note: the newly-active provider and its tools load at SESSION START, so they're fully wired in the NEXT `hermes` session, not the one that ran the activation. Say so rather than implying they're live this turn.

## Live verification (do not skip)

Prove the connection with a real authenticated round-trip, using **Hermes' own interpreter** so the plugin's deps are on the path:

- Hermes launcher is a shell wrapper; read it to find the interpreter:
  `head -5 $(command -v hermes)` → typically `~/.hermes/hermes-agent/venv/bin/python`
- Install a missing client into THAT venv: `<hermes-venv-python> -m pip install '<client>>=<ver>'`
  (Hermes auto-installs some clients on session start, but doing it now makes the connection ready immediately.)
- Make the CHEAPEST authenticated call (e.g. a `get_version()` / health endpoint), not just an import. A version string coming back from the remote host proves key + URL + network all work; an import success does not.

Pitfall: run verification scripts from a FILE, not a shell heredoc — heredocs trip the terminal command parser and can dump unrelated AGENTS.md context. See `references/hindsight-connection.md` for a worked end-to-end connection example (the reusable probe pattern and the exact gotchas).

## Writing/reading provider memory programmatically

Beyond connecting, the user may ask to push a batch of notes INTO a provider's store, or verify what's in it. For Hindsight this is the `hindsight-client` API (`client.retain(bank_id, content=..., context=..., tags=..., metadata=...)`, `client.recall(bank_id, query)`). Method signatures, the `content=` (not `text=`) gotcha, verifying a write via `recall().results`, and CHUNKING large ingests to avoid output-limit blowups are in `references/hindsight-retain-recall.md`. General rule: after any write, read it back and confirm your own metadata (a `success=True` response is necessary but not sufficient proof it's retrievable).

## Reporting

State which of the three layers was actually the gap, what you changed (with the exact `hermes config set ...`), and the live-verification evidence (the version/health response). Distinguish a probe-script bug from a real connection failure — a wrong function signature is not a broken connection.
