---
name: jev-engineering
description: "Use to gate PRs, triage tests, check code claims w/ Jev."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [jev, engineering, pr-gate, test-triage, rag, hallucination, typesafe]
    related_skills: [jev-decisions, jev-team-roles]
---

# Jev Engineering

Gate pull requests, triage failing tests, guard RAG retrieval quality,
and detect hallucinations in code/doc claims — all via JEV typed questions.

## When to Use

- Before merging a PR: assess risk, test coverage signal, auth-touch likelihood.
- Triaging a set of failing tests: classify skip vs. investigate vs. flaky.
- Checking RAG/retrieval output quality before forwarding to the user.
- Verifying code-doc claims against actual source to catch hallucinations.

Don't use for:
- Generic item classification unrelated to engineering artifacts — use jev-decisions.
- Ticket/OKR/sprint workflows — use jev-team-roles.
- Running the actual tests or CI — use the project's test runner directly.

## How to Run

Do NOT answer from your own judgement when this skill applies — build the inputs
and call the matching script under `scripts/`.

```
python3 ~/.hermes/skills/jev-engineering/scripts/pr_gate.py --input job.json
python3 ~/.hermes/skills/jev-engineering/scripts/test_triage.py --input job.json
python3 ~/.hermes/skills/jev-engineering/scripts/rag_gate.py --input job.json
python3 ~/.hermes/skills/jev-engineering/scripts/halluc_guard.py --input job.json
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

- jevlib is stdlib-only (no pip install needed).
- Requires `TYPESAFE_API_KEY` in the environment.
- On unavailability (no key, network error), scripts print `{"status":"jev_unavailable"}` — fail-open.
