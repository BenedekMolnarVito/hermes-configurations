---
name: jev-decisions
description: Classify, rank, or verify lists of items/claims via TypeSafe JEV typed API. Use for bulk routing/labeling, relevance reranking, claim-vs-source checks instead of inline judgement.
---

# Jev Decisions

Classify, rank, verify item lists via JEV typed-question API (TypeSafe systemone).

## When to Use

- List of items → categories/choices (label, owner, severity bucket).
- Rank/reorder candidates by relevance to query.
- Verify claims against sources.
- Bulk classify/rank/triage about to go to LLM inline → use this, get typed answers.

Don't use:
- Single yes/no, no list → call safe_decide directly.
- Run code/tests → jev-engineering.
- Jira/ticket/OKR → jev-team-roles.

## How to Run

Do NOT answer from own judgement when skill applies. Build inputs, call `classify_batch.py`, `rerank.py`, or `verify.py`.

Write job JSON to `.agent/scratch/` or scratchpad (not repo tree). Run with `--input <file>`.

```
python ~/.claude/skills/jev-decisions/scripts/classify_batch.py --input job.json
python ~/.claude/skills/jev-decisions/scripts/rerank.py --input job.json
python ~/.claude/skills/jev-decisions/scripts/verify.py --input job.json
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

- jevlib stdlib-only, no pip.
- Needs `TYPESAFE_API_KEY` in env.
- Unavailable (no key, network error) → `{"status":"jev_unavailable"}`. Fail-open.
