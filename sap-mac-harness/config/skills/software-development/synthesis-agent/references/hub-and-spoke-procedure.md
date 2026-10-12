# Hub-and-Spoke Enforcement Procedure

> **FOR THE ORCHESTRATOR (hub agent in the main session).**
> This procedure enforces the hub-and-spoke pattern for every multi-agent workflow.

## The Rule

**Every multi-spoke subagent batch result MUST pass through a synthesis agent before the orchestrator acts on it.**

Subagents = spokes. Orchestrator = hub. Synthesis agent = the condensation layer between spokes and hub.

## Step-by-Step Enforcement

### 1. Dispatch Subagents (Spokes)

- Spawn all parallel subagents in a single `delegate_task` batch (one call, N tasks).
- Each subagent has fresh, isolated context (no shared memory).
- Each subagent returns a raw summary to the orchestrator.

### 2. Collect Raw Summaries

- Gather ALL subagent summaries. Do NOT process them yet.
- Do NOT let any subagent result enter your reasoning without synthesis.

### 3. Dispatch Synthesis Agent (The Hub Gate)

Dispatch a **quick-tier** subagent (`model: anthropic--claude-4.5-haiku, provider: custom`) with:

- **Goal:** `Condense the raw subagent summaries into a structured handoff packet for the orchestrator.`
- **Context:** The original goal + all raw subagent summaries + any constraints/acceptance criteria.
- **Reference:** this skill's `references/synthesis-prompt-template.md` (the synthesis agent reads it).

> If the batch is large (5+ subagents with verbose output), write the raw summaries to a scratch file and tell the synthesis agent: `Read <path> first.` This prevents stream timeouts (large inline dispatch prompts time out).

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
- The synthesis agent is ALWAYS in the loop for multi-spoke batches.

## When synthesis is NOT required

- A single spoke that already returns one crisp distilled result (a finding, a diff summary, pass/fail). Synthesis exists to reconcile a BATCH and keep context lean; a lone distilled result goes straight to the hub.

## What Breaks Without This

- **Context bloat:** Raw subagent reports flood the main session.
- **Missed contradictions:** Without synthesis, the orchestrator may not notice when subagents disagree.
- **Handoff leakage:** Subagents may omit or embellish; synthesis forces factual extraction.
- **No hub gating:** The orchestrator acts on partial/raw info instead of synthesized facts.

## Transient failure during orchestration

A spoke (or the synthesis child) that hits 429 / rate-limit / provider error / insufficient-credits is transient infra, never a verdict. Mark it DEFERRED, salvage its partial (live_transcript tail, git status/diff, scratch files), send the distilled partial forward. Recover: backoff 10s → re-dispatch a NEW child with the same file-based brief + condensed partial attached → escalate tier once if the cheap pool stays congested → defer to later. Max 3 retries. Never absorb a rate-limited reviewer's or implementer's work inline (self-review with no fresh context is not a review). Disclose every DEFERRED item in the final report.
