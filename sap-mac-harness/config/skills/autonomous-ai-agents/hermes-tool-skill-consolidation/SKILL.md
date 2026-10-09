---
name: hermes-tool-skill-consolidation
description: "Consolidate Hermes tools/skills to cut context bloat; sharpen triggers; scope subagents. (The single consolidation skill — covers measuring prompt-size, trimming toolsets, archiving/merging skills, and subagent tool-scoping.)"
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos, linux, windows]
metadata:
  hermes:
    tags: [hermes, consolidation, toolsets, skills, delegation, subagents, context-budget, prompt-size]
    related_skills: [hermes-agent, hermes-model-tier-routing]
---

# Hermes Tool & Skill Consolidation

Reduce per-turn context bloat and tool/skill confusion in a Hermes profile, and spawn subagents scoped to only the tools their domain needs. Measure before and after; change nothing without the user's explicit OK on the concrete list.

## The four layers (know which one actually costs context)

Before proposing cuts, separate these — conflating them wastes effort on the wrong target:

1. Toolsets — REAL per-turn cost. Enabled toolsets inject full tool-schema JSON into the system prompt every turn. This is where "too many tools confuses the model" is literally true. ~40 KB / ~27 tools is typical.
2. Skills — near-zero per-turn cost. Only the one-line name+description is always-on (the skills index, ~9 KB for ~100 skills). Full SKILL.md loads on demand via skill_view. The real harm from too many skills is AMBIGUOUS TRIGGERS → wrong skill loaded, not context size.
3. Plugins — disabled = ZERO cost. `hermes plugins list` shows ~60 bundled but only the `enabled` ones load. A huge plugin list is almost always a red herring.
4. MCP servers — usually DEFERRED (lazy). Their tools cost context only when invoked (they show in the deferred-tool catalog, not the always-on schemas). Confirm with prompt-size before treating an MCP as bloat.
5. Memory providers — REAL per-turn cost when auto-recall is on. Hindsight injects up to `recall_max_tokens` (default 4096) of recalled memories into the system prompt every turn. This is a SEPARATE budget from tool schemas and often overlooked. For optimization see `hermes-agent` skill → `references/memory-provider-optimization.md`.

## Measure first (always)

```bash
hermes prompt-size            # system prompt total, skills index, tool schemas (count + bytes), per-toolset breakdown
hermes prompt-size --json     # machine-readable; toolsets_breakdown, skills_breakdown
hermes tools list             # enabled/disabled toolsets
hermes plugins list           # only 'enabled' matters
hermes mcp list               # servers; `hermes mcp test <name>` lists a server's tools + count
hermes skills list            # counts by origin (bundled/agent/hub/local)
hermes curator usage          # per-skill origin + use/view/patch counts + last_activity
```

Capture the baseline numbers, do the work, re-run `hermes prompt-size`, and report the delta. The headline metrics: system prompt total, skills index bytes, tool-schema bytes/count.

## Workflow

1. Inventory + measure (commands above). Identify: enabled toolsets the user does not use in this profile; skill trigger OVERLAPS (clusters where several descriptions could match one intent); true duplicates (bundled skill vs a superpowers/plugin equivalent).
2. Present the concrete per-item list and ASK before modifying anything. The user's standing rule is "ask before modifying any tools/skills." Show exact skill names and the exact toolsets to disable.
3. Apply only what was approved (see mechanics below).
4. Re-measure and report the delta + what's reversible and how.

## Mechanics (all reversible)

Toolsets — disable unused ones (biggest real win):
```bash
hermes tools disable tts          # recover: hermes tools enable tts
```
Keep what the user's work needs. For a software engineer doing coding/testing/automation/research: keep terminal, file, web, skills, delegation, memory, session_search, context_engine, clarify, cronjob, todo, connections, browser, computer_use. Drop tts (and code_execution only if terminal+delegation fully cover it).

Skills — sharpen ambiguous triggers (edit description frontmatter). Only patch AGENT-created or local skills freely; editing a BUNDLED skill marks it user-modified (flag those for the user first). Give each overlapping skill a disjoint "Use when … (other case -> other-skill)." trigger.

Skills — archive unused/creative/duplicate (see references/archiving-skills.md for why curator can't do bundled and the move-folder method).

Delegation policy — write a standing "delegate context-heavy work" rule to ~/.hermes/SOUL.md so heavy reads/extractions/triage/verification run in isolated subagent context. See references/subagent-scoping.md.

## Subagent scoping — narrow tools per domain (user priority)

Goal: each subagent has access to ONLY the tools its domain needs. The honest capability split in the current Hermes build is in references/subagent-scoping.md — READ IT before promising deterministic narrowing. Summary:

- The model-facing delegate_task does NOT expose a `toolsets` or `model` argument. Children INHERIT the parent's toolsets minus a hardcoded blocklist. You cannot narrow a delegate_task child's toolset from the tool call.
- Deterministic narrowing IS possible by spawning a fresh hermes process with an explicit toolset: `hermes chat -q '<goal>' -t 'terminal,file' -m <model> -s <skill>`. That child literally cannot use tools outside `-t`.
- Probabilistic fallback (when you must use delegate_task): scope the child's goal/context tightly to its domain so it only reaches for domain tools, and pre-narrow the PARENT session toolset (children inherit the reduced set).

## Hard invariants

- Never hand-edit config.yaml; use `hermes config set` / `hermes tools`.
- Never delete skills; archive (move) so it's reversible.
- Ask before modifying tools/skills; show the exact list.
- Measure with prompt-size before and after — claims about "less bloat" must be backed by the delta.

## Pitfalls (do not optimize the wrong layer)

- `hermes skills opt-out` is all-or-nothing and `opt-out --remove` DELETES every unmodified bundled skill — too blunt for selective hiding; use the move-to-`skills_disabled/` method (references/archiving-skills.md) instead.
- Protected skills (bundled, hub, pinned, user-owned) are off-limits to autonomous CONTENT edits — moving a directory to hide it is fine (reversible filesystem op), but editing a bundled skill's body marks it user-modified and drifts it from upstream. Only sharpen descriptions of AGENT-owned skills freely.
- After archiving/merging a skill, clean dangling `related_skills:` cross-references in the survivors that point at the removed name — a dead xref misleads future trigger selection.
- Toolset changes take effect on a NEW session (/reset), never mid-conversation (prompt-caching invariant).
- Verify a merge survivor actually COVERS the archived skill's duty before moving it. Skills that merely share a topic but carry runtime-specific mechanics (e.g. a Hermes delegate_task orchestration layer vs a Claude-Code Task-tool superpowers skill) are COMPLEMENTS, not duplicates — sharpen their triggers, don't archive. Merging distinct capabilities is over-engineering.
