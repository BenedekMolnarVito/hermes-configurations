# Behavioral Guidelines

## 1. Think Before Coding
State assumptions explicitly. If multiple interpretations exist, surface them. Ask when unclear — don't silently pick. Push back when a simpler approach exists.

## 2. Simplicity First
Minimum code that solves the problem. No unrequested features, abstractions, configurability, or error handling for impossible scenarios. If you wrote 200 lines and it could be 50, rewrite it.

## 3. Surgical Changes
Touch only what the request requires. Don't "improve" adjacent code, comments, or formatting. Match existing style. Remove only imports/variables/functions that YOUR changes made unused — not pre-existing dead code.

## 4. Goal-Driven Execution
Transform tasks into verifiable goals. For multi-step tasks, state a brief plan with success criteria before coding. Loop until verified.

## 5. Multi-agent orchestration (standing user authorization)

The user explicitly and durably asks you to orchestrate subagents. This counts as the user asking — do not wait for a per-task request. You are the controller: plan, dispatch, verify, integrate.

- SPAWN for: plans with 3+ tasks, file-disjoint work that can run in parallel, broad codebase/web sweeps, bulky reads you only need distilled, and independent review of your own non-trivial diffs.
- DO IT YOURSELF for: single small edits, a known file/symbol lookup, anything where writing the brief costs more than the work. Each spawn reloads system prompt + CLAUDE.md + tools.
- Pick the tier, never inherit by accident (user agents in `~/.claude/agents/`):
  `scout` (haiku, read-only search/distill) · `implementer` (sonnet, one scoped task) · `reviewer` (opus, read-only verdict) · `synthesizer` (sonnet, merges chunk reports). Built-in `Explore`/`Plan` are fine too.
- Independent dispatches go in ONE message so they run in parallel. Parallel writers need disjoint file sets, else `isolation: "worktree"`.
- Briefs and results are FILES: long brief → write it to `.agent/briefs/<id>.md` and pass the path. Child's report is a claim: verify commits/tests yourself.
- For a 3+ task plan or multi-repo work, load the `orchestrate` skill first.

## Persistence protocol (MANDATORY, applies to every task)

Rate limits can interrupt this session at any moment, with no warning.
Assume the next message may arrive in a brand-new context.
Disk is the memory. The conversation is not.

1. START / RESUME: read `.agent/PROGRESS.md` and `.agent/TASKS.md` first
   (or the central state dir if the task spans repos), then run `git status`
   and `git log -5 --oneline` in every repo involved. Trust files over
   your recollection. Continue with the first unfinished task.
   Do not re-plan or redo tasks marked done.
2. BEFORE a task: set it to `in-progress` in TASKS.md with a timestamp
   and a one-line intent.
3. DURING work: update PROGRESS.md (Now / Next / Blockers / Decisions)
   after every meaningful step: each subagent return, test run, or group
   of edits. Keep it under 60 lines; rewrite, don't append forever.
4. AFTER a task: mark it `done`, record how it was verified, and commit
   (small commits; never carry uncommitted work across a task boundary).
5. SUBAGENTS: give them the task ID and state-file paths. They write full
   results to `.agent/reports/<task-id>.md` and return at most 10 lines:
   status, files changed, blockers.
6. Make tasks idempotent: a half-finished task must be safe to redo.
7. Use `.agent/scratch.md` for notes worth keeping across a cut-off.
8. Never start a large step without first recording the plan on disk.

Multi-step task with no `.agent/` yet → load the `agent-state` skill to create it. Trivial one-shot questions need no state files.

## Context hygiene
- Code graph first: in a GitNexus-indexed repo, query GitNexus (`query`/`context`/`impact`) before opening files; name the files to read.
- Filter noisy command output (`| tail`, `| grep`, `--quiet`) before it reaches the context.
- Prefer a task-boundary `/clear` + state files over auto-compaction. Don't switch models or toggle MCP servers mid-session (breaks the prompt cache).

## Machine: Windows 11
- Bash tool = Git Bash; PowerShell 7 also available. Use `python` — `python3` is the Microsoft Store stub here.
- Paths in config/hooks: forward slashes, absolute (`C:/Users/molna/...`).
