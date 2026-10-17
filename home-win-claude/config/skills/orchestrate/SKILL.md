---
name: orchestrate
description: Controller playbook for multi-agent work in Claude Code — executing a plan with 3+ tasks via subagents, parallelizing file-disjoint tasks (worktrees), chunked bulk reads/research (map-reduce), parallel reviews, and multi-repo orchestration that survives rate-limit cut-offs. Load at the START of such work, not mid-loop.
---

# Orchestrate

You = CONTROLLER: plan, dispatch, verify, integrate. Subagents do bounded work.
State: `.agent/` (one repo) or `~/agent-work/<project>/` (multi-repo). Missing → load `agent-state` first.

## 1. Resume check (every start/wakeup)
1. Read `PROGRESS.md` + `TASKS.md`. Per repo: `git status`, `git log -5 --oneline`, `git worktree list`.
2. Reconcile: `in-progress` + commit exists → check "Verify by", mark `done`. `in-progress`, no commit, no live child → finish yourself from disk (written files usually right), don't re-dispatch from scratch.
3. `reports/<id>.md` = recovery point for child that died after writing it.

## 2. Plan → task table
- Row: ID, Repo, one-line desc, **Verify by** (command or observable check).
- Build each task's file-touch set. Parallel IFF sets disjoint (check intersection, don't eyeball). Shared files → same task or serial.
- Plan on disk BEFORE any dispatch.

## 3. Dispatch
- Tier by work: `scout` (haiku) search/distill · `implementer` (sonnet) one scoped task · `reviewer` (opus) large/high-risk verdicts · `synthesizer` (sonnet) reduce. `model` param only to escalate one dispatch.
- Brief = exact paths/symbols, exact change, verify command, done format, stop conditions ("assumption mismatch → BLOCKED"). Can't write that without exploring → explore first (self or scout). Never "figure out X and fix it".
- Long brief (>~40 lines, code, diffs) → `.agent/briefs/<id>.md`; prompt = "Read <path> first, authoritative" + task id + report path.
- Carry forward only what later task can't know: interfaces earlier tasks made, your rulings. Never paste session history.
- Independent dispatches in ONE message. Parallel writers, same repo → `isolation: "worktree"` each, merge after.
- Caveman I/O: briefs, prompts, reports terse (no articles/filler, fragments OK); code/paths/errors exact. Hook enforces on child side.
- Return contract (hook-injected when `.agent/` exists): full result → `.agent/reports/<id>.md`, ≤10-line reply.

## 4. Verify (child DONE = claim)
- `git show --stat <sha>`: scope right, no leak from other task, tree clean.
- Run verify yourself. Record known pre-existing failing test by NAME at start; "same count, different test" = regression.
- Parallel children report divergent test counts → ignore; only your full run after all land counts.
- After each return: TASKS.md (`done` + how verified), PROGRESS.md. Commit per task.

## 5. Review
- Per-task review only for non-trivial diffs; scale reviewer to risk.
- Final whole-branch review (one `reviewer`): full diff file + briefs; point at files two tasks both touched + round-trip paths (serialize/export/copy). Per-task reviews miss cross-task gaps.
- Fix wave: all Critical/Important → ONE fix dispatch + ONE scoped re-review.

## 6. Bulky I/O → map-reduce, not your context
Huge file, many URLs, tree-wide sweep: chunk → one `scout` per chunk → `reports/<id>-chunkN.md` → one `synthesizer` → final artifact. Keep only final path + short summary.

## 7. Parallel review of N artifacts
N read-only reviews → N `reviewer`/`scout` in one message, own report path each, then one synthesis. Reviewers never edit.

## 8. Multi-repo
- State in `~/agent-work/<project>/`; TASKS.md has `Repo` column.
- Launch: `claude --add-dir <repoA> --add-dir <repoB>` (via `claude-resumable.ps1` for auto-resume).
- One worktree per repo/task for parallel children → cut-off can't leave shared tree half-edited.

## 9. Finish
Remove worktrees (`git worktree remove <path>; git worktree prune`), delete merged task branches. Offer merge / push+PR / keep, then WAIT — push/merge to shared base = user's call. List your rulings so user can overturn.

## Pitfalls
- Re-dispatch "incomplete" task while child still running → two writers, one branch.
- `git worktree add` on checked-out branch fails; serial tasks work in place.
- Big diffs/briefs inlined in prompts bloat every later turn. Paths, not payloads.
- Spawn for 1-file edit: spawn cost > work.
