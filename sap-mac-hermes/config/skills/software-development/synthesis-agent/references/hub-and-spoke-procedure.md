# Hub-and-Spoke Enforcement Procedure

> **FOR THE ORCHESTRATOR (hub agent in the main session).**
> This procedure enforces the hub-and-spoke pattern for every multi-agent workflow.

## The Rule

**Every multi-spoke subagent batch result MUST pass through a synthesis agent before the orchestrator acts on it.**

Subagents = spokes. Orchestrator = hub. Synthesis agent = the condensation layer between spokes and hub.

## The Dispatch Gate (straight-line spokes)

The synthesis gate governs what comes BACK; this gate governs what goes OUT. A spoke's speed is fixed before it is spawned: subagents have isolated context — they cannot see this session, earlier spokes, or the plan — so anything the brief does not state, the child must discover, and discovery is what turns a 2-minute task into a 20-minute one.

### 1. Split THINK from EXECUTE

- THINK = explore, diagnose, design, decide, debug unknowns. Runs at the hub (preferred for bounded questions) or a deep-tier spoke. Never on a quick spoke.
- EXECUTE = apply a known change, fetch/extract, run verification, mechanical edits. Quick or standard tier.
- Never combine in one child: "find what's wrong and fix it" handed to a quick spoke guarantees wandering. The hub (or a deep spoke) finds it and hands the fix down as a recipe.

### 2. Verdict packet — how thinking hands back down

A THINK spoke (or the hub's own diagnosis) returns a VERDICT PACKET, not a narrative:

- **Verdict** — one line: the root cause or decision.
- **Recipe** — numbered exact steps: file paths + symbols, exact edits/commands, in order.
- **Evidence** — paths/lines/outputs the verdict rests on.
- **Open questions** — anything unresolved the EXECUTE step must NOT guess.

The hub (optionally via the synthesis agent) fans the recipe out as EXECUTE briefs.

### 3. Straight-line brief checklist (every EXECUTE dispatch)

- **WHAT** — the exact action; before -> after for edits.
- **WHERE** — absolute paths + symbols/anchors; branch/worktree; files the child must not touch.
- **VERIFY** — exact commands + expected results.
- **DONE** — the return format (short status + artifact paths).
- **STOP** (hard rule) — on any assumption mismatch (file missing, state differs, gate already failing), stop and return BLOCKED + the mismatch. No improvising, no self-assigned research, no scope widening.

Pre-dispatch test: *Could a competent fresh engineer finish this with zero questions and zero files opened beyond those named?* If not, it is a THINK task — finish the thinking, then dispatch the recipe.

### 4. Wandering is a brief defect

If a spoke's live transcript shows exploration the brief never asked for (reading unlisted files, re-diagnosing, re-planning), do not wait it out: stop the child, fix or re-tier the brief, re-dispatch. Blame the brief, not the spoke.

## Step-by-Step Enforcement

### 1. Dispatch Subagents (Spokes)

- Each brief passes the Dispatch Gate above (straight-line checklist; THINK work is done before, not inside, the child).
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

- **Wandering spokes:** an under-specified dispatch turns a quick task into open-ended exploration — slow, expensive, and unpredictable.
- **Context bloat:** Raw subagent reports flood the main session.
- **Missed contradictions:** Without synthesis, the orchestrator may not notice when subagents disagree.
- **Handoff leakage:** Subagents may omit or embellish; synthesis forces factual extraction.
- **No hub gating:** The orchestrator acts on partial/raw info instead of synthesized facts.

## Transient failure during orchestration

A spoke (or the synthesis child) that hits 429 / rate-limit / provider error / insufficient-credits is transient infra, never a verdict. Mark it DEFERRED, salvage its partial (live_transcript tail, git status/diff, scratch files), send the distilled partial forward. Recover: backoff 10s → re-dispatch a NEW child with the same file-based brief + condensed partial attached → escalate tier once if the cheap pool stays congested → defer to later. Max 3 retries. Never absorb a rate-limited reviewer's or implementer's work inline (self-review with no fresh context is not a review). Disclose every DEFERRED item in the final report.
