---
name: synthesis-agent
description: "Condense subagent results into a structured handoff packet for the hub orchestrator, enforcing hub-and-spoke architecture and keeping main context lean."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [multi-agent, orchestration, synthesis, hub-and-spoke, context-management, subagent, condensation]
    related_skills: [bugfix-orchestrator, hermes-tool-skill-consolidation, merge-reconciler, plan]
---

# Synthesis Agent Skill

## Overview

A standalone synthesis agent skill that enforces the hub-and-spoke multi-agent architecture by condensing all subagent results into a structured handoff packet before the orchestrator (hub agent) acts on them. This skill is reusable across any orchestration workflow — bugfix-orchestrator, multi-agent code review, parallel research campaigns, etc.

## Trigger

Use this skill when: You are an orchestrator (hub agent) who has just received raw summaries from one or more subagents (spokes) and need to condense them into a structured handoff packet before making the next delegation decision.

**Use when synthesizing subagent results in ANY orchestration workflow; not only bugfix-orchestrator.**

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

1. **Hub gating:** No subagent result enters the orchestrator's reasoning without passing through synthesis first (small-batch exception in Enforcement Rules).
2. **Ephemeral subagents:** Spokes have fresh, isolated context. Their raw reports are discarded after synthesis.
3. **Factual extraction only:** The synthesis agent extracts and condenses; it does not re-interpret or embellish.
4. **Contradiction surfacing:** If two subagents disagree, the synthesis agent flags it explicitly in the handoff packet.
5. **Main context stays lean:** Only the condensed handoff packet touches the orchestrator's context window.

## How to Invoke

After collecting raw subagent summaries, spawn a synthesis-agent subagent:

```
delegate_task(
  tasks=[{
    goal="Condense the raw subagent summaries into a structured handoff packet for the orchestrator.",
    context="<ORIGINAL GOAL>\n\nSUBAGENT SUMMARIES:\n<subagent_a_summary>\n\n<subagent_b_summary>\n\nCONSTRAINTS: <acceptance_criteria>",
    output_schema={
      type: "object",
      required: ["handoff_packet"],
      properties: {
        handoff_packet: { type: "string", description: "The condensed handoff packet markdown." }
      }
    }
  }]
)
```

### Dispatch Context Format

The synthesis agent's context must contain exactly:

1. **ORIGINAL GOAL** — the orchestrator's original task (verbatim)
2. **SUBAGENT SUMMARIES** — all raw subagent reports (verbatim, not re-summarized)
3. **CONSTRAINTS** — acceptance criteria, file ownership rules, verification commands

> If the batch produced large reports, write them to a scratch file and point the synthesis agent to it: `Read <absolute_path> first.`

### Tier Routing

The synthesis agent is dispatched at the **quick** tier by default — it performs condensation, not reasoning. It should be fast and cheap.

### If the synthesis dispatch itself is rate-limited

A 429 on the synthesis child is transient infra, not a license to skip synthesis. Backoff 10s, re-dispatch a new synthesis agent with the same input + condensed partials; escalate to **moderate** once if the quick pool stays congested (correct condensation outranks tier purity). Max 3 retries. Subagent inputs that arrived as salvaged partials must be marked DEFERRED with their source (transcript tail, diff) so the packet records what is provisional. On a large batch (5+ subagents) never fall back to orchestrator-side summarizing from memory — defer the decision and retry the synthesis later.

## The Handoff Packet

The synthesis agent returns a markdown handoff packet with these sections:

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

## Integration with Other Skills

- **bugfix-orchestrator:** Stages 2, 3, 7, 8 — invoke synthesis after every subagent batch. The skill's text says "Synthesis agent condenses subagent outputs" — this skill makes it explicit and mandatory.
- **hermes-tool-skill-consolidation:** Subagent scoping rules apply. The synthesis agent inherits the parent's toolset minus the hardcoded blocklist (no delegate_task, no memory, etc.). Quick tier is appropriate.
- **merge-reconciler:** Can use a synthesis agent to condense both sides' diffs + intent summaries into a handoff packet before the reconciler begins.
- **plan:** The plan skill references subagent-driven-development for execution. Each subagent batch in that workflow should pass through synthesis.

## Enforcement Rules

These are hard invariants the orchestrator (you) must enforce:

1. **No bypass on real batches:** After a delegate_task batch, the very next delegate_task MUST be a synthesis-agent call; no acting on raw summaries. Exception — a small batch (1–2 children) whose short raw reports are already in hand may be condensed by the orchestrator directly from verified tool output (a synthesis child costs more than it saves); write the packet in the standard sections yourself and note the skipped synthesis dispatch in the final report. Any larger batch never bypasses synthesis.
2. **Fresh context:** The synthesis agent gets the raw summaries as context, not the full conversation history.
3. **Discard raw reports:** After synthesis, remove raw subagent summaries from main context (or reference them from a scratch file only).
4. **Decision logging:** When the orchestrator makes a decision from the handoff packet, note which section of which packet informed it.
5. **Contradiction escalation:** If the handoff packet flags contradictions, the orchestrator must resolve them (dispatch a new subagent) before proceeding.

## Caveman-Compress

The synthesis agent applies caveman-compress rules (see Hindsight memory):

- Strip all filler, hedging, and prose explanations.
- Keep file paths, line numbers, exact values, and verification outputs.
- Preserve attribution: every finding cites which subagent produced it.
- Output in telegraphic key-value form where possible.
- Global toggle: `JEVGUARD_CAVEMAN=off` disables compression if needed.

## Pitfalls to Avoid

- **Synthesis as summary:** The synthesis agent must EXTRACT and CONDENSE, not summarize. Each finding must cite a source subagent.
- **Missing context:** If the orchestrator's original goal isn't passed to the synthesis agent, it cannot distinguish signal from noise.
- **Over-compression:** Compressing so hard that the orchestrator can't make an educated next decision. The packet must have enough context (file paths, exact claims, constraints).
- **Source citation loss:** Inline hyperlinks in subagent prose are frequently dropped during synthesis. The synthesis agent must convert links to explicit path citations.
- **Large inline prompts:** Writing all raw summaries inline in the synthesis agent's context causes stream timeouts. Use scratch files for batches with 5+ subagents.
