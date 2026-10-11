# Hub-and-Spoke Enforcement Procedure

> **FOR THE ORCHESTRATOR (hub agent in the main session).**
> This procedure enforces the hub-and-spoke pattern for every multi-agent workflow.

## The Rule

**Every subagent result MUST pass through a synthesis agent before the orchestrator acts on it.**

Subagents = spokes. Orchestrator = hub. Synthesis agent = the condensation layer between spokes and hub.

## Step-by-Step Enforcement

### 1. Dispatch Subagents (Spokes)

- Spawn all parallel subagents in a single `delegate_task` batch.
- Each subagent has fresh, isolated context (no shared memory).
- Each subagent returns a raw summary to the orchestrator.

### 2. Collect Raw Summaries

- Gather ALL subagent summaries. Do NOT process them yet.
- Do NOT let any subagent result enter your reasoning without synthesis.

### 3. Dispatch Synthesis Agent (The Hub Gate)

Dispatch a **quick-tier** subagent with:

- **Goal:** `Condense the raw subagent summaries into a structured handoff packet for the orchestrator.`
- **Context:** The original goal + all raw subagent summaries + any constraints/acceptance criteria.
- **Reference:** This skill's `references/synthesis-prompt-template.md` (the synthesis agent reads it).

> If the batch is large (5+ subagents with verbose output), write the raw summaries to a scratch file and tell the synthesis agent: `Read <path> first.` This prevents stream timeouts (see Hindsight memory: large inline dispatch prompts cause timeouts).

### 4. Receive Handoff Packet

- The synthesis agent returns ONLY the condensed handoff packet (see template).
- Discard the raw summaries from context (or move them to a scratch file reference).
- The orchestrator reasons ONLY from the handoff packet.

### 5. Make Educated Judgments

- From the handoff packet, decide the next actions.
- Flag any contradictions, blockers, or missing info.
- Dispatch the NEXT batch of subagents based on SYNTHESIZED information only.

### 6. Repeat

- After the next subagent batch completes, return to Step 2.
- The synthesis agent is ALWAYS in the loop.

## What Breaks Without This

- **Context bloat:** Raw subagent reports flood the main session.
- **Missed contradictions:** Without synthesis, the orchestrator may not notice when subagents disagree.
- **Handoff leakage:** Subagents may omit or embellish; synthesis forces factual extraction.
- **No hub gating:** The orchestrator acts on partial/raw info instead of synthesized facts.

## Integration with Existing Skills

- **bugfix-orchestrator:** Already mentions "Synthesis agent condenses subagent outputs." This procedure makes that explicit and mandatory.
- **hermes-tool-skill-consolidation:** Subagent scoping rules apply (children inherit parent toolset minus blocklist). Synthesis agent uses quick tier.
- **merge-reconciler:** Uses neutral third-party pattern; synthesis agent can also serve as the neutral condenser for merge conflict reports.

## Caveman-Compress Integration

The synthesis agent should apply caveman-compress rules when condensing:
- Strip all filler, hedging, and prose explanations.
- Keep file paths, line numbers, exact values, and verification outputs.
- Preserve attribution: every finding cites which subagent produced it.
- Output as telegraphic key-value pairs where possible.

> Global toggle: `JEVGUARD_CAVEMAN=off` disables caveman compression if it causes issues.
