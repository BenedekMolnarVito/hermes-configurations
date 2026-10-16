# Dispatching the loop to a small-model subagent

The browser navigation loop is designed to be **inherited by a small model**. Each
decision is small and structured (one operation, one target, from an observed
list), so a cheap model running the loop against the chrome-devtools MCP achieves
goals at a fraction of the cost of driving every click on a frontier model.

Use this path when the standalone jev agent (`jev-agent.md`) isn't available
(no API keys) but the chrome-devtools MCP is.

## The pattern

1. **Frontier model (you): scope + delegate.** Turn the user's request into a
   crisp, verifiable goal and a start URL. Then spawn a subagent on a small model
   with the Agent tool, pointing it at this skill.
2. **Small-model subagent: run the loop.** It executes observe→decide→act→
   re-observe→iterate using the MCP tools, within a step budget, and reports back
   the outcome plus the concrete evidence it saw.
3. **Frontier model (you): verify.** Do not trust a bare "done". Check the
   reported evidence; if unclear, take one `take_snapshot` yourself and confirm
   the goal is really satisfied before telling the user it's complete.

## Dispatch template

Spawn with the Agent tool, `subagent_type: "general-purpose"`, `model: "haiku"`
(or another small model). Keep the goal narrow and verifiable — the small model
is good at executing a clear objective, not at deciding what the objective is.

```
model: haiku
description: "Drive browser to <goal>"
prompt: |
  Load the skill at
  /Users/C5418860/.claude/skills/web/browser-navigation-loop/SKILL.md
  and follow its observe→decide→act→re-observe loop using the chrome-devtools
  MCP tools. Do NOT dispatch further subagents — YOU run the loop inline.

  START URL: <url>
  GOAL: <single, concrete, verifiable goal>

  Rules:
  - One operation + one target per cycle. Take a fresh take_snapshot after each
    action and confirm the page changed as expected.
  - Don't repeat satisfied steps; a typed query still needs its suggestion
    clicked; submit search fields before opening results; set every requested
    filter.
  - Step budget: ~40 actions. If 3 consecutive non-wait actions change nothing,
    stop and report BLOCKED.
  - Never invent personal data not given in the goal.

  When finished, report:
  - status: DONE or BLOCKED
  - the concrete on-page EVIDENCE you relied on (visible text, applied filters,
    confirmation, final URL)
  - a short list of the actions you took
```

Fill `<url>` and `<goal>` before dispatching. For a multi-page errand, give the
subagent the whole goal — the loop decomposes it step by step; you don't need to
pre-plan the clicks.

## Why delegate instead of running it yourself

- **Cost.** A frontier model per click is the expensive mistake jev was built to
  avoid. The decision is small; the model running it should be too.
- **Parallelism.** Independent browser goals can go to several small-model
  subagents at once (one page each via `new_page`/isolated contexts), while you
  stay free to orchestrate and verify.
- **Focus.** Your judgement is best spent on goal interpretation and outcome
  verification — the parts a small model genuinely can't do — not on reading
  snapshots and emitting clicks.

## Caveats

- A small model is more likely to stall on jev's known-hard cases (shadow DOM,
  cross-origin frames, canvas, uploads, pop-ups, complex keyboard widgets). If the
  subagent reports BLOCKED there, consider taking over inline for the stuck step.
- Give one concrete goal per subagent. Vague or multi-interpretation goals are
  where small models drift — that disambiguation is your job before dispatch.
