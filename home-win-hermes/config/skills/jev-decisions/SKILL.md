---
name: jev-decisions
description: "Use to classify, rank, or verify item lists via Jev."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [jev, decisions, classify, rank, verify, typesafe]
    related_skills: [jev-engineering, jev-team-roles]
---

# Jev Decisions

Classify, rank, or verify item lists using the JEV typed-question API
(TypeSafe systemone endpoint).

## When to Use

- You have a list of items to classify into categories or choices (e.g. route each
  item to a label, owner, or severity bucket).
- You need to rank / reorder candidates by relevance to a query.
- You need to verify or spot-check factual claims against their sources.
- A bulk classify/rank/triage job is about to be handed to an LLM inline — use this
  instead to get typed, structured answers.

Don't use for:
- Single yes/no questions that don't involve a list — call safe_decide directly.
- Tasks that require executing code or running tests — that is jev-engineering.
- Jira/ticket/OKR specific workflows — that is jev-team-roles.

## How to Run

Do NOT answer from your own judgement when this skill applies — build the inputs
and call `scripts/classify_batch.py`, `scripts/rerank.py`, or `scripts/verify.py`.

Write the job to a JSON file and invoke the matching script with `--input <file>`.

```
# Classify items
python3 ~/.hermes/skills/jev-decisions/scripts/classify_batch.py --input job.json

# Rerank candidates
python3 ~/.hermes/skills/jev-decisions/scripts/rerank.py --input job.json

# Verify claims
python3 ~/.hermes/skills/jev-decisions/scripts/verify.py --input job.json
```

### classify_batch job shape

```json
{
  "items": ["item 1", "item 2", "item 3"],
  "question": "How would you classify this?",
  "options": {"optA": "description A", "optB": "description B"}
}
```

Output: `{"status":"ok","results":[{"item_index":0,"choice":"optA","confidence":0.9}, ...]}`

### rerank job shape

```json
{
  "query": "your search query",
  "candidates": ["candidate 1", "candidate 2"]
}
```

Output: `{"status":"ok","results":[{"candidate":"...","noul":0.9}, ...]}` sorted desc by noul.

### verify job shape

```json
{
  "claims": [
    {"claim": "X causes Y", "source": "Paper says X causes Y."}
  ]
}
```

Output: `{"status":"ok","results":[{"index":0,"verdict":"supports","confidence":0.95}]}`

## Notes

- jevlib is stdlib-only (no pip install needed).
- Requires `TYPESAFE_API_KEY` in the environment.
- On unavailability (no key, network error), scripts print `{"status":"jev_unavailable"}` — fail-open.
