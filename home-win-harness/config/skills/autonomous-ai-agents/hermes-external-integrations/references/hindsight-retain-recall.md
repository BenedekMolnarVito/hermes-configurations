# Hindsight — retaining & recalling memory units via the client API

When the user asks to push a batch of notes/lessons INTO a Hindsight bank (not just connect it), use the `hindsight-client` Python API directly with Hermes' venv interpreter. This is the write/read-back companion to `references/hindsight-connection.md` (which covers connect + activate + `get_version()` proof).

## Setup (same as connection probe)

```python
import os
env = {}
with open(os.path.expanduser("~/.hermes/.env")) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
import hindsight_client as hc
client = hc.Hindsight(base_url=env["HINDSIGHT_API_URL"], api_key=env["HINDSIGHT_API_KEY"])
BANK = env["HINDSIGHT_BANK_ID"]
```

Run from a FILE with `~/.hermes/hermes-agent/venv/bin/python`, never a heredoc (heredocs trip the terminal parser).

## retain() — store a memory unit

Exact signature (client v api 0.9.2):
```
retain(bank_id, content, timestamp=None, context=None, document_id=None,
       metadata=None, entities=None, resolve_entities=None, tags=None,
       update_mode=None, retain_async=False, operation_id=None) -> RetainResponse
```

GOTCHA: the text parameter is `content=`, NOT `text=`. Passing `text=` raises `TypeError: unexpected keyword argument`.

- `metadata` values must be str→str (e.g. `{"slug": "...", "type": "project"}`).
- `context` is a free-text label attached to every unit in the batch (e.g. "FAA engineering lessons") — good for grouping/recall relevance.
- `tags` is a `list[str]`; merged with the provider's default `retain_tags`.
- Success looks like `RetainResponse(success=True, bank_id=..., items_count=1, ...)`. Read `.success`, not just "no exception."
- Hindsight does server-side extraction: one retained document becomes one or more knowledge units of `type: 'world'` (facts), each carrying your `metadata` and the original `document_id`. So recall returns MORE units than you retained — expected.

## recall() — read back / verify

Signature is positional bank-first: `recall(bank_id, query, types=None, max_tokens=4096, budget='mid', ...)`.
Calling `recall(query, bank_id=...)` raises `TypeError: missing 1 required positional argument: 'query'` — probe bug, not a connection failure.

Response is a pydantic `RecallResponse`. The hits are in `.results` (a list); also has `.entities`, `.chunks`, `.source_facts`, `.trace`, and `.to_prompt_string()`. Each result dict has `text`, `type`, `context`, `document_id`, `metadata`. To verify a write landed, recall a distinctive phrase and confirm your `metadata.slug` shows up:
```python
r = client.recall(bank_id=BANK, query="distinctive phrase from the note", max_tokens=1200, budget="high")
print(r.model_dump()["results"][0])
```
Retain may be async server-side; a short `sleep` before recall avoids a false empty.

## Chunking (avoid output-limit blowups)

When retaining many/large units, do it in small batches (2–3 units per script run) that append results to a checkpoint file (e.g. `~/.hermes/hindsight_ingest_results.jsonl`), rather than one giant call. Put the shared retain loop + client in one module and `import` it from per-batch scripts (guard the loop under `if __name__ == "__main__":` so import doesn't re-retain). This survives a timeout mid-batch and keeps each call's stdout small.

## Async / cleanup noise

The client uses aiohttp under the hood; after a sync script you may see `Unclosed client session / connector` warnings on stderr. Harmless — call `client.close()` at the end and/or filter those lines from output. They are not errors.
