---
name: jev-engineering
description: Gate PRs, triage failing tests, check RAG relevance, detect hallucinated code/doc claims via TypeSafe JEV. Use before merging, when tests fail, or when verifying claims against source.
---

# Jev Engineering

Gate PRs, triage failing tests, guard RAG quality, detect hallucinations. JEV typed questions.

## When to Use

- Before PR merge: risk, test-coverage signal, auth-touch likelihood.
- Failing tests set: classify skip / investigate / flaky.
- RAG/retrieval output quality check before forwarding to user.
- Code-doc claims vs actual source → catch hallucinations.

Don't use:
- Generic list classification, non-engineering → jev-decisions.
- Ticket/OKR/sprint → jev-team-roles.
- Running tests/CI → project test runner.

## How to Run

Do NOT answer from own judgement when skill applies. Build inputs, call matching script.

Write job JSON to `.agent/scratch/` or scratchpad (not repo tree).

```
python ~/.claude/skills/jev-engineering/scripts/pr_gate.py --input job.json
python ~/.claude/skills/jev-engineering/scripts/test_triage.py --input job.json
python ~/.claude/skills/jev-engineering/scripts/rag_gate.py --input job.json
python ~/.claude/skills/jev-engineering/scripts/halluc_guard.py --input job.json
```

### pr_gate job shape

```json
{
  "title": "feat: add auth refresh",
  "diff_summary": "Modifies token flow, adds tests for refresh path.",
  "files_changed": ["src/auth.ts", "tests/auth.test.ts"]
}
```

Output: `{"status":"ok","results":{"risk_score":1.2,"has_tests_noul":0.8,"touches_auth_noul":0.9}}`

### test_triage job shape

```json
{
  "tests": [
    {"name": "test_login", "failure": "AssertionError: expected 200 got 401"},
    {"name": "test_flaky_net", "failure": "Timeout after 5s"}
  ]
}
```

Output: `{"status":"ok","results":[{"name":"...","action":"investigate","confidence":0.9}, ...]}`

### rag_gate job shape

```json
{
  "query": "What is the retry policy?",
  "retrieved": ["Chunk about retry...", "Unrelated chunk..."]
}
```

Output: `{"status":"ok","results":[{"chunk_index":0,"relevant_noul":0.85}, ...]}`

### halluc_guard job shape

```json
{
  "claims": [
    {"claim": "Function X returns bool", "source": "def X() -> int: ..."}
  ]
}
```

Output: `{"status":"ok","results":[{"index":0,"verdict":"contradicts","confidence":0.9}]}`

## Notes

- jevlib stdlib-only, no pip.
- Needs `TYPESAFE_API_KEY` in env.
- Unavailable (no key, network error) → `{"status":"jev_unavailable"}`. Fail-open.
