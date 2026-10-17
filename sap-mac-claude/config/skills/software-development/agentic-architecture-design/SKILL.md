---
name: agentic-architecture-design
description: "Use when designing agentic systems or agent architecture."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [agentic-ai, agentic-architecture, orchestration, subagents, mcp, claude, design]
    related_skills: [auto-discoverable-skills]
---

# Agentic System Architecture — Design Guidance

Authoritative, drill-tested guidance for designing agentic systems with Claude:
the agentic loop, multi-agent orchestration, subagent isolation, tool/MCP
design, workflow enforcement, prompting for structured output, and context /
reliability management. Backed by a knowledge base of 30 lessons + 257
multi-choice drill examples (correct AND incorrect answers, with the trap family
each wrong answer represents) synthesized from the Claude Certification
(Architect) guide and classified with TypeSafe Jev.

## When to Use

Load this skill and consult the KB when the task involves DESIGNING or REVIEWING
an agentic system, for example:
- Building an agent loop / deciding how it terminates.
- Choosing an orchestration pattern (sequential / parallel / pipeline / dynamic /
  hub-and-spoke) or deciding single-agent vs multi-agent.
- Spawning subagents, scoping their tools, or passing context between agents.
- Enforcing a rule that "must always" hold (compliance, security, financial).
- Designing tool descriptions / MCP integration / structured output contracts.
- Handling context-window growth, escalation, error propagation, provenance.

### Don't use for
- Pure prompt wording with no architecture decision (just write the prompt).
- Non-agentic app code, data pipelines, infra, or CI unrelated to agents.
- SAP/FAA-specific agent plumbing — that lives in the CFAAI wiki
  (`fin-analyst-agent`, `kyma-agent-dpg-setup`), not here. This skill is the
  vendor-neutral design layer; cross-reference but don't duplicate.

## How to use it — DO NOT answer from memory alone

When this skill applies, do NOT reason the answer purely from your own
judgement. Query the knowledge base first with the helper, then apply its
principles and cite the specific lesson / drill example.

The helper script lives in THIS SKILL's own directory (NOT in the KB directory).
Run it by its absolute path — do not guess a relative path:

    python3 ~/.hermes/skills/software-development/agentic-architecture-design/scripts/query_kb.py "<topic or design question>"

(The `skill_view` result for this skill also lists `scripts/query_kb.py` under
`linked_files`; the `skill_dir` field is the absolute directory the script is in.
Use `<skill_dir>/scripts/query_kb.py`.)

It searches the KB (lesson bodies + 257 drill examples) and prints the most
relevant lessons, the keyed principles, and matching drill examples showing the
correct answer and each incorrect answer with its trap family — exactly the
disambiguation you need when choosing between plausible designs. The script
prints the KB paths it resolved on its first line.

The KB itself is a SEPARATE location from the script:
`/Users/C5418860/temp/claude-cert-guide/kb/` (30 lesson markdown files +
`index.md`), with drill data at
`/Users/C5418860/temp/claude-cert-guide/drill/questions_by_lesson.json`. Override
with `AGENTIC_KB_ROOT=/path/to/claude-cert-guide` if it moved. The synthesized
concept pages are also in the CFAAI wiki under `[[agentic-architecture-guide]]`.

If the script prints that the KB is absent (different machine and no override),
fall back to the wiki hub page and the core decision rules below — but only
after actually running the script, never assume absence.

## Core decision rules (fast reference; the KB has the full treatment)

- **Loop control = `stop_reason`.** Continue on `tool_use`, terminate on
  `end_turn`; append tool results to history each turn. Never parse natural
  language, never check `content[0].type == "text"`, never use an iteration cap
  as the PRIMARY stop (caps are safety nets only). Anything but `end_turn` =
  "not done, check why".
- **"Must always" / compliance / security / financial → code, not prompts.**
  Use PreToolUse/PostToolUse hooks or a prerequisite gate. Prompts are
  probabilistic; a routing classifier does NOT fix in-agent execution.
- **Multi-agent = hub-and-spoke.** Coordinator decomposes/sequences/aggregates;
  subagents are isolated (no shared memory) so pass all context explicitly; no
  peer-to-peer. Coordinator needs `Task`/`Agent` in `allowedTools` to delegate.
- **Scope tools tightly** (4–5 role-focused, not 18) — selection reliability
  degrades with tool count.
- **Handoff = escalation to a human** who sees only the structured summary
  (ID, facts, root cause, amount, recommended action); no agent-to-agent handoff
  primitive. A classifier score under a per-category threshold is a valid
  escalation trigger; an agent's self-reported confidence is not.
- **Structured output via tool use / JSON schema**, with self-check fields; retry
  with error feedback and a cap, then degrade or escalate.
- **Stale context → fresh session + curated summary**, not more context.

## Pitfalls

- Don't recommend an iteration cap as the fix for premature termination — fix
  the `stop_reason` check.
- Don't recommend a stronger prompt where a guarantee is required — use a hook/gate.
- Don't assume subagents can read the coordinator's context.
- 6 drill keys are Jev-contested (flagged in the KB) — when the helper surfaces
  one, verify against primary Anthropic docs before relying on it.
