---
name: orchestrate
description: Controller playbook for multi-agent work in Claude Code — executing a plan with 3+ tasks via subagents, parallelizing file-disjoint tasks (worktrees), chunked bulk reads/research (map-reduce), parallel reviews, and multi-repo orchestration that survives rate-limit cut-offs. Load at the START of such work, not mid-loop.
---

# Orchestrate

You are the CONTROLLER. You plan, dispatch, verify and integrate; subagents do bounded work.
State lives in `.agent/` (single repo) or `~/agent-work/<project>/` (multi-repo). If it does not exist, load `agent-state` first.

## 1. Resume check (every start, every wakeup)
1. Read `PROGRESS.md` + `TASKS.md`. Then per repo: `git status`, `git log -5 --oneline`, `git worktree list`.
2. Reconcile: `in-progress` task whose commit exists → verify its "Verify by", mark `done`. `in-progress` with no commit and no live child → finish it yourself from what's on disk (files written are usually right) rather than re-dispatching from scratch.
3. A report in `reports/<id>.md` is the recovery point for a child that died after writing it.

## 2. Plan → task table
- Every task row: ID, Repo, one-line description, **Verify by** (a command or observable check).
- Build each task's file-touch set. Two tasks may run in parallel IFF their sets are disjoint (check the intersection, don't eyeball). Shared files → same task or serial.
- Record the plan on disk BEFORE dispatching anything.

## 3. Dispatch
- Tier by work, not habit: `scout` (haiku) search/distill · `implementer` (sonnet) one scoped task · `reviewer` (opus) verdicts on large/high-risk diffs · `synthesizer` (sonnet) reduce. Use the `model` param only to escalate a specific dispatch.
- Brief = exact paths/symbols, the exact change, verify command, done format, stop conditions ("assumption mismatch → return BLOCKED"). If you can't write that without exploring, explore first (yourself or a scout) — never dispatch "figure out X and fix it".
- Long brief (>~40 lines, embedded code, diffs) → write `.agent/briefs/<id>.md`; dispatch prompt says "Read <path> first, it is authoritative" + task id + report path.
- Carry forward only what a later task can't know: interfaces earlier tasks created and your rulings. Never paste session history.
- Independent dispatches in ONE message (parallel). Parallel writers on the same repo → `isolation: "worktree"` each, merge after.
- Return contract (also injected by the `subagent_contract` hook when `.agent/` exists): full result to `.agent/reports/<id>.md`, ≤10-line reply.

## 4. Verify (the child's DONE is a claim)
- `git show --stat <sha>`: scope correct, nothing from another task leaked, tree clean.
- Run the verify command yourself. Record a known pre-existing failing test by NAME at start; "same count, different test" is a regression.
- Parallel children report divergent test counts — ignore them; only your full run after all land counts.
- Update TASKS.md (`done` + how verified) and PROGRESS.md after each return. Commit per task.

## 5. Review
- Per-task review only for non-trivial diffs; scale the reviewer to the diff's risk.
- Final whole-branch review (one `reviewer`): hand it the full diff file + task briefs and point it at files two tasks both touched and at round-trip paths (serialize/export/copy) — per-task reviews can't see cross-task gaps.
- Fix wave: batch all Critical/Important findings into ONE fix dispatch + ONE scoped re-review.

## 6. Bulky I/O → map-reduce, not your context
Huge file, many URLs, tree-wide sweep: split into chunks → one `scout` per chunk writing `reports/<id>-chunkN.md` → one `synthesizer` producing the final artifact. You keep only the final path + a short summary.

## 7. Parallel review of N artifacts
N independent read-only reviews → N `reviewer`/`scout` dispatches in one message, each with its own report path, then one synthesis. Don't let reviewers edit.

## 8. Multi-repo
- State in `~/agent-work/<project>/`; TASKS.md has a `Repo` column.
- Launch: `claude --add-dir <repoA> --add-dir <repoB>` (via `claude-resumable.ps1` for auto-resume).
- One worktree per repo/task for parallel children so a cut-off can't leave a shared tree half-edited.

## 9. Finish
Remove worktrees (`git worktree remove <path>; git worktree prune`), delete merged task branches. Present merge / push+PR / keep and WAIT — pushing or merging a shared base is the user's call. List your rulings so the user can overturn them.

## Pitfalls
- Re-dispatching a task that looks incomplete while its child is still running → two writers on one branch.
- `git worktree add` for the currently checked-out branch fails; serial tasks work in place.
- Inlining big diffs/briefs into dispatch prompts: bloats every later turn. Paths, not payloads.
- Spawning for a 1-file edit: the fixed spawn cost exceeds the work.
