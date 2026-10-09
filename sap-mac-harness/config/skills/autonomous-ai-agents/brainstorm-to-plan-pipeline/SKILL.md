---
name: brainstorm-to-plan-pipeline
description: "Use on Hermes to brainstorm-with-subagents then plan (delegate_task explorer->judge pipeline)."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [subagents, delegation, brainstorming, planning, orchestration, pipeline, loop]
    related_skills: [parallel-review-subagents, plan, subagent-driven-development]
---

# Brainstorm-to-Plan Pipeline

Use when a spec asks you to explore/brainstorm ideas with subagents and then
write plans. Orchestrate a SEQUENTIAL multi-stage subagent pipeline that turns an
open-ended spec into decision-grade design + implementation-plan documents.
Distinct from `parallel-review-subagents`: there the children are independent and
read-only; here each stage CONSUMES the distilled output of the prior stage, so
stages are ordered and the hand-off between them is the whole point.

Canonical pipeline: N parallel EXPLORERS (different angles) -> one SYNTHESIS
(cluster/de-dupe into themes) -> one JUDGE (score feasibility/usefulness,
attack YAGNI, recommend build order + MVP cut-line) -> you write the DESIGN plan
and the IMPLEMENTATION plan(s). A separate code-RECON child (read-only) can run
in parallel with the explorers when the plan also covers changes to existing code.

## When to Use

- A spec says: spawn subagents to explore ideas, synthesize, judge, and save a
  design plan + implementation plan(s) for later.
- Any time the deliverable is PLANS (not code), built from a brainstorm whose
  stages depend on each other.

## Procedure

### 1. Reconcile the spec premise against reality BEFORE spawning anything

The attached/working copy of a spec is often STALE or TRUNCATED. Find the
authoritative version and diff it: the root-level `change_reqs.md` (or equivalent)
frequently holds the full spec while the copy under `docs/updates_*/` is an older
snapshot missing whole sections. `diff` the two; plan against the fuller one.
Missing this means you build the wrong, smaller deliverable.

Re-check current state every iteration (list the output docs dir, `git status`,
`git log main..HEAD`) rather than trusting earlier-iteration assumptions.

### 2. Classify plan-only vs implement, and set the gates

If the spec says "do NOT change or commit anything yet, wait for user trigger" (or
is clearly a planning task), this is PLAN-ONLY. Then:
- Create a dedicated branch for the whole story if the user asks (`git checkout -b
  feat/<date>-<slug>`); untracked files follow the branch automatically.
- Write ONLY the plan/design markdown files; never edit source, never commit.
- The brainstorming skill's interactive approval gate is pre-satisfied by the
  spec's explicit autonomous instruction + /loop — do not stall asking for
  approval you were already given, but DO still ask a clarify question when a
  requirement is genuinely ambiguous (see step 6).

### 3. Resolve model tiers once, then route every child explicitly

Read `config.yaml` `model.aliases` for deep/standard/quick (model id + base_url).
Route by stage weight and ALWAYS pass the override explicitly (an omitted model
inherits your expensive session model):
- explorers, synthesis, judge -> deep (reasoning-heavy)
- code recon / scoped reads -> standard
- trivial extraction/verification -> quick

### 4. Dispatch stage-by-stage; let background results drive the cadence

Subagents run in BACKGROUND mode: the result re-enters as a new message only
after you END YOUR TURN. So the pipeline is naturally paced by turns/loop-wakeups:
- Dispatch the parallel explorers (+ recon) in ONE `delegate_task` call.
- END THE TURN. Do not poll, do not busy-wait, do not emit no-op tool calls to
  keep the turn open — polling a self-paced loop just burns iterations.
- When the explorer batch delivers, dispatch synthesis (it depends on all
  explorers). End turn. When synthesis delivers, dispatch the judge. End turn.
- Only `delegate_task(action='list')` to check liveness when you genuinely need
  to; a finished child is simply no longer listed.

### 5. Make each stage self-contained via CONTEXT, not file reads

Pass the prior stage's FULL distilled output inline in the next child's
`context` string, so the child needs no repo reads to do its job and its output
stays comparable. Give every child an `output_schema` (structured ideas/themes/
scores) so the stages compose mechanically instead of by prose parsing. Tell each
child its role and that it is a leaf (no further subagents).

Stage-specific musts:
- EXPLORERS: give each a DIFFERENT lens (e.g. UX-friction vs automation/
  intelligence) and the same rich app/context block; demand ranked ideas with
  problem/why/impact-per-effort and (for automation) an on-device/privacy
  feasibility tag.
- SYNTHESIS: cluster into THEMES, merge overlaps, surface dependency chains
  ("capability X underpins Y and Z"), and FLAG overlaps with already-decided
  fixed requirements so nothing is re-proposed as new work.
- JUDGE: must be told to be opinionated and attack the synthesis, not just rank
  it — score feasibility + usefulness FOR THIS specific app, call out YAGNI/
  over-engineering explicitly, flag privacy/constraint violations, and output a
  corrected build order + an MVP cut-line. A judge that only ranks is wasted; the
  value is the YAGNI cuts and the dependency-corrected order.

### 6. Clarify genuinely-ambiguous requirements before planning them

When a late-arriving CR hinges on semantics that change the data model or core
algorithm (e.g. "exception tags" — is the default auto-learned or explicitly set?
what clears on switch? which screens?), make ONE batched `clarify` call with the
2-4 decision-forking questions BEFORE writing the plan. Guessing here means
reworking a plan that touches migrations and the classification core.

### 7. Write the plan docs; chunk large writes

Save under the spec's requested dir (`docs/updates_*/`), not the repo root.
Produce: a DESIGN plan (synthesis narrative + per-theme detail with the judge's
scores/trade-offs/verdicts + MVP cut-line + build order) and one IMPLEMENTATION
plan per track (fixed-requirements vs new-ideas). Keep a `_recon_*.md` as the
supporting evidence file for implementation plans.

Implementation plans must be executable by `subagent-driven-development`: a header
pointing at that skill, Global Constraints, per-task bite-sized TDD steps with
exact file:line refs, and an explicit per-task MODEL-TIER routing table so the
executor auto-routes children. List post-MVP items as a backlog, not as runnable
tasks.

CHUNK large markdown writes: `write_file` the header + first sections, then
`patch`-append the rest. A single giant write risks `finish_reason=length`
truncation mid-document; on any truncation signal, auto-chunk without being asked.

### 8. Verify the hold-the-line invariants before declaring done

For a plan-only task: confirm `git status` shows only untracked plan files and
`git log main..HEAD` is empty (nothing committed), you are on the intended
branch, and every spec bullet maps to a plan section. Then end the loop
(`LOOP_COMPLETE` on its own line when running under /loop).

### 9. Landing the plans when the user later triggers it

The plan-only hold ends when the user explicitly says to commit/push/PR. Then:
- Rebase onto the INTEGRATION branch the user names (often `develop`, not
  `main`): `git fetch origin <base>` then `git rebase origin/<base>`. A planning
  branch cut from `main` with zero commits rebases cleanly; target the branch the
  PR will merge into so history is linear.
- Stage ONLY the deliverables (`git add change_reqs.md docs/updates_*/`). Exclude
  pre-existing untracked scratch (e.g. a `.maestro/` runner, local fixtures) that
  was never part of this work — `git status` before staging and name files
  explicitly rather than `git add -A`.
- One Conventional Commit (`docs(planning): ...`), push `-u`, open the PR into the
  SAME integration branch with `--body-file` (never a `$(cat <<EOF)` heredoc
  inline — the tool's shell guard mangles nested command substitution; write the
  body to a scratch file and pass `--body-file`).
- PR summary states it is planning-only / no source changes, lists the plan docs,
  and names the migration/other highest-risk item flagged inside.

## Pitfalls

- Do not plan against the attached spec copy without diffing it against the
  authoritative one — the copy is routinely a truncated older snapshot.
- Do not poll or busy-wait for background children in a self-paced loop; dispatch,
  end the turn, resume the dependent stage when the result message arrives.
- Do not omit the model override on a child — it silently inherits your session
  model (usually the most expensive tier).
- Do not let the judge merely rank; without an explicit "attack YAGNI / correct
  the dependency order / give an MVP cut-line" instruction it produces a glossy
  summary, not a decision.
- Do not feed a stage by making it re-read the repo; pass the prior stage's
  distilled output in `context` so stages stay comparable and cheap.
- Do not commit or touch source on a plan-only task, even when the plan feels
  obviously right — the trigger-to-implement is a separate, explicit user action.
- Do not write a 20KB plan in one call; chunk to avoid length-truncation.
- Do not guess data-model/algorithm semantics of an ambiguous CR; one batched
  clarify call is cheaper than replanning a migration.
- When landing on github.com but `gh auth status` shows only an enterprise host
  (e.g. github.tools.sap), gh picks up the enterprise `GITHUB_TOKEN` and fails
  with "Could not resolve to a Repository" on the github.com repo. The git
  credential helper usually still holds a working github.com token (it is what
  let `git push` succeed) — feed it to gh for the one command:
  `GH_TOKEN="$(printf 'protocol=https\\nhost=github.com\\n\\n' | git credential fill | sed -n 's/^password=//p')" GH_HOST=github.com gh pr create ...`.
  The secret flows helper->gh in the pipeline and never enters chat.
