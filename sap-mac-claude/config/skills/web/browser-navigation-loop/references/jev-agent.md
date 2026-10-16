# The standalone jev-ultrafast agent

`browser-use/jev-ultrafast` is the reference implementation of this skill's loop.
It is the embodiment of the core idea: **a small model plus structured DOM
observation is enough to navigate the browser efficiently and cheaply.** You do
not need a large reasoning model in the hot loop — TypeSafe's *Jev* model picks
one operation + one target per observation in a single network round trip, and a
small text LLM writes a field value only when the operation is `TYPE_TEXT`.

## Why this exists as a fast path

Driving the loop yourself (reading snapshots, deciding, acting) works and needs
no API keys, but every decision cycle costs a full model turn. The jev agent
instead makes **one cheap request per decision cycle** against a model
specialized for operation/target selection. Benchmarks from the repo:

- Zürich→London on Google Flights: **~7.1 s** end to end (model calls, generated
  text, and loading waits included).
- Median browser-protocol calls per run dropped from 1,092 → 101 versus a
  screenshot-driven baseline; median task time 9.45 s → 7.09 s (~25% faster).
- Wikipedia "open this article": ~2.8 s. Local hotel search/filter: ~1.9 s.

These are three repeats of a few tasks on one profile — a demonstration of the
approach, not a broad reliability benchmark.

## When to choose it over the Claude-driven loop

Choose the standalone agent when:
- The task is a well-scoped, verifiable browser goal ("search X", "open the
  article about Y", "fill this form and submit") and you want it done fast/cheap.
- You can supply `TYPESAFE_API_KEY` and a text-model key.
- You will independently verify the outcome afterward (a `DONE` from the agent is
  not proof — see below).

Stay with the Claude-driven MCP loop when:
- No API keys are available.
- The task needs judgement the small policy won't have (ambiguous goals,
  reading/reasoning over page content, deciding *what* the goal even is).
- You hit jev's known limits: shadow DOM, cross-origin frames, canvas UIs,
  uploads, pop-up tabs, nested scrolling, arbitrary keyboard widgets.

## Requirements

- `uv` (the repo uses `uv sync` / `uv run`).
- Chrome, connected via [Browser Harness](https://github.com/browser-use/browser-harness)
  (installed by `uv sync`; run `uv run browser-harness --doctor` if it needs
  connecting, and allow remote debugging in Chrome when prompted).
- `TYPESAFE_API_KEY` — the operation/target policy. See https://docs.typesafe.ai.
- `TEXT_MODEL_API_KEY` — an OpenAI-compatible key for the text helper. The repo's
  example uses an OpenRouter key with `inception/mercury-2.5`, reasoning disabled.
  DeepSeek / Gemini / GLM also work via the OpenAI-compatible endpoint.

## Install

Run `scripts/setup_jev.sh` (clones into `~/.cache/jev-ultrafast` by default and
runs `uv sync`), or do it by hand:

```bash
git clone https://github.com/browser-use/jev-ultrafast.git
cd jev-ultrafast
uv sync
cp .env.example .env   # then fill in TYPESAFE_API_KEY and TEXT_MODEL_API_KEY
```

## Run

Headless task run (what a subagent should call) — `scripts/run_jev.py` wraps this:

```bash
cd <jev-repo>
uv run --env-file .env python examples/run.py \
  --url   'https://en.wikipedia.org/wiki/Main_Page' \
  --goal  'Find and open the Wikipedia article about Gödel'\''s incompleteness theorems.'
```

Library form (for embedding in a script):

```python
from jev_ultrafast import Agent

with Agent(url, goal) as agent:
    for state in agent.run():      # yields observable state each step
        print(state["elapsed_ms"], state["status"])
    final = agent.state["status"]  # "done" or "blocked"
```

Interactive inspector (for a human to watch the numbered elements, operation and
target probabilities, and executed actions):

```bash
uv run jev        # then open http://127.0.0.1:8766 → Start demo → Run automatically
```

## Verifying the outcome — not optional

jev's own policy will emit `DONE` when it believes the goal is met, but the repo
is explicit that **a `DONE` choice still requires independent outcome
verification.** After any run, confirm against the real page: the requested
route/date/filters are visibly applied, the expected result/confirmation is
present. If you dispatched the agent from a subagent, have the subagent report
the concrete evidence, and re-check with a `take_snapshot` if anything is unclear.

## Safety properties worth knowing

The agent never turns model output into selectors, coordinates, shell commands,
or executable JavaScript — every executed target resolves to a DOM node that was
actually observed, and the executor re-checks freshness and click occlusion
before input. Text-helper output must parse as a tiny JSON object before it is
typed. Credentials stay server-side in the text helper. This is what makes it
safe to hand a natural-language goal to a small model without it inventing
dangerous actions.
