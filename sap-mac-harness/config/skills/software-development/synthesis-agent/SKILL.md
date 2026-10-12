---
name: synthesis-agent
description: "Use to condense a batch of subagent results."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [multi-agent, orchestration, synthesis, hub-and-spoke, context-management, subagent, condensation]
    related_skills: [parallel-review-subagents, subagent-execution-orchestration, hermes-tool-skill-consolidation, merge-reconciler, plan]
---

# Synthesis Agent Skill

## Overview

Enforces the hub-and-spoke multi-agent architecture by condensing all subagent (spoke) results into a structured handoff packet before the orchestrator (hub) acts on them. Reusable across any orchestration workflow — multi-agent code review, parallel research, SDD execution, bugfix orchestration.

## When to Use

Use when: you are the orchestrator (hub) and have just received raw summaries from one or more subagents (spokes) and need to condense them into a structured handoff packet before the next delegation decision.

**Applies to synthesizing subagent results in ANY orchestration workflow, not one specific pipeline.**

## Architecture

```
Orchestrator (hub, main session)
  │
  ├── delegates → Subagent A (spoke) ──┐
  ├── delegates → Subagent B (spoke) ──┤
  ├── delegates → Subagent C (spoke) ──┤
  │                                     │
  │   raw summaries                     │
  │                                     │
  └── delegates → Synthesis Agent ────────┐
                                          │
                                    Handoff Packet
                                          │
                                          ▼
                              Orchestrator decides next actions
```

### Key Principles

1. **Hub gating:** No subagent result enters the orchestrator's reasoning without passing through synthesis first.
2. **Ephemeral subagents:** Spokes have fresh, isolated context. Their raw reports are discarded after synthesis.
3. **Factual extraction only:** The synthesis agent extracts and condenses; it does not re-interpret or embellish.
4. **Contradiction surfacing:** If two subagents disagree, the synthesis agent flags it explicitly in the packet.
5. **Main context stays lean:** Only the condensed handoff packet touches the orchestrator's context window.

## How to Invoke

After collecting raw subagent summaries, spawn a synthesis-agent subagent at the **quick** tier (condensation, not reasoning):

```
delegate_task(tasks=[{
  goal: "Condense the raw subagent summaries into a structured handoff packet for the orchestrator.",
  context: "<ORIGINAL GOAL>\n\nSUBAGENT SUMMARIES:\n<a_summary>\n\n<b_summary>\n\nCONSTRAINTS: <acceptance_criteria>",
  output_schema: { type: "object", required: ["handoff_packet"],
    properties: { handoff_packet: { type: "string", description: "The condensed handoff packet markdown." } } }
}])
```

On THIS instance, pass the quick tier explicitly: `model: anthropic--claude-4.5-haiku, provider: custom` (resolve from `model.aliases.quick` in config.yaml — do not hardcode if the alias changes).

### Dispatch Context Format

The synthesis agent's context must contain exactly:

1. **ORIGINAL GOAL** — the orchestrator's original task (verbatim)
2. **SUBAGENT SUMMARIES** — all raw subagent reports (verbatim, not re-summarized by you)
3. **CONSTRAINTS** — acceptance criteria, file ownership rules, verification commands

> If the batch produced large reports (5+ verbose subagents), write them to a scratch file and point the synthesis agent to it: `Read <absolute_path> first.` Large inline dispatch prompts time out the stream.

### If the synthesis dispatch itself is rate-limited

A 429 on the synthesis child is transient infra, not a license to skip synthesis. Backoff 10s, re-dispatch a new synthesis agent with the same input + condensed partials; escalate to **standard** once if the quick pool stays congested (correct condensation outranks tier purity). Max 3 retries. Inputs that arrived as salvaged partials must be marked DEFERRED with their source (transcript tail, diff). On a large batch (5+ subagents) never fall back to orchestrator-side summarizing from memory — defer the decision and retry synthesis later.

## The Handoff Packet

The synthesis agent returns a markdown handoff packet with these sections (full template in `references/synthesis-prompt-template.md`):

| Section | Purpose |
|---------|---------|
| Goal Restatement | 1-sentence restatement of the original goal |
| Subagent Roster | Table of subagents, tiers, tasks, status, duration |
| Key Findings | Bullet list; each finding cites subagent ID, file path, line number |
| Decisions Required | Table: decision question, options, evidence, recommendation |
| Blockers / Ambiguity | Table: which subagent is blocked, issue, what's needed |
| Next-Action Plan | Table: step, action, target subagent type, tier, context needed |
| Condensed Evidence | Compact snippets: test outputs, DOM dumps, file paths |

The orchestrator reads ONLY this packet and nothing else from the subagent batch.

## Enforcement Rules

Hard invariants the orchestrator (you) must enforce:

1. **No bypass:** After a delegate_task batch of 2+ spokes, the next delegate_task should be a synthesis-agent call before acting on raw summaries. (A single spoke returning one crisp distilled result does not need synthesis — synthesis exists to reconcile MANY spokes and keep context lean.)
2. **Fresh context:** The synthesis agent gets the raw summaries as context, not the full conversation history.
3. **Discard raw reports:** After synthesis, reference raw subagent summaries from a scratch file only; reason from the packet.
4. **Decision logging:** When you make a decision from the packet, note which section informed it.
5. **Contradiction escalation:** If the packet flags contradictions, resolve them (dispatch a new subagent) before proceeding.

## Full Procedure

See `references/hub-and-spoke-procedure.md` for the step-by-step enforcement loop and `references/synthesis-prompt-template.md` for the exact prompt + output format to hand the synthesis subagent.

## Pitfalls to Avoid

- **Synthesis as summary:** The synthesis agent must EXTRACT and CONDENSE, not summarize. Each finding must cite a source subagent.
- **Missing context:** If the original goal isn't passed, the agent cannot distinguish signal from noise.
- **Over-compression:** Compressing so hard the orchestrator can't make an educated next decision. Keep file paths, exact claims, constraints.
- **Source citation loss:** Convert inline links in subagent prose to explicit path citations.
- **Large inline prompts:** 5+ raw summaries inline causes stream timeouts — use a scratch file.
- **Synthesizing a single spoke:** Overkill. Synthesis is for reconciling a batch; one distilled result goes straight to the hub.