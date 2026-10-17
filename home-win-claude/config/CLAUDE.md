# Rules

## 1. Think first
State assumptions. Many readings → surface them. Unclear → ask, no silent pick. Simpler way exists → push back.

## 2. Simple
Min code that solves it. No unasked features, abstractions, config, or handling for impossible cases. 200 lines that could be 50 → rewrite.

## 3. Surgical
Touch only what request needs. No "improving" nearby code/comments/format. Match style. Remove only imports/vars/funcs YOUR change orphaned, not old dead code.

## 4. Goal-driven
Task → verifiable goal. Multi-step → brief plan + success criteria before code. Loop until verified.

## 5. Multi-agent (standing user authorization)
User durably wants subagent orchestration. Counts as asked — no per-task request needed. You = controller: plan, dispatch, verify, integrate.
- SPAWN: 3+ task plans, file-disjoint parallel work, broad code/web sweeps, bulky reads needing only distill, independent review of own non-trivial diffs.
- SELF: single small edit, known file/symbol lookup, brief costs more than work. Each spawn reloads system prompt + CLAUDE.md + tools.
- Pick tier, never inherit by accident (`~/.claude/agents/`): `scout` (haiku, read-only search/distill) · `implementer` (sonnet, one scoped task) · `reviewer` (opus, read-only verdict) · `synthesizer` (sonnet, merge chunk reports). Built-in `Explore`/`Plan` OK.
- Independent dispatches in ONE message → parallel. Parallel writers need disjoint files, else `isolation: "worktree"`.
- Briefs + results = FILES: long brief → `.agent/briefs/<id>.md`, pass path. Child report = claim: verify commits/tests yourself.
- 3+ task plan or multi-repo → load `orchestrate` skill first.
- Inter-agent I/O = caveman, always, no ask needed: write briefs/prompts/reports terse (drop articles, filler, pleasantries; fragments OK; `→` for causality). Keep exact: code, paths, symbols, commands, errors, numbers. Hook appends same rule to every Agent prompt. User-facing chat stays normal unless `/caveman`.

## Persistence (MANDATORY, every task)
Rate limit can cut session any moment. Next message may be fresh context. Disk = memory, conversation ≠.
1. START/RESUME: read `.agent/PROGRESS.md` + `.agent/TASKS.md` (or central state dir if multi-repo), then `git status` + `git log -5 --oneline` per repo. Trust files over recall. Continue first unfinished task. Don't re-plan/redo done tasks.
2. BEFORE task: TASKS.md → `in-progress` + timestamp + one-line intent.
3. DURING: update PROGRESS.md (Now/Next/Blockers/Decisions) after each meaningful step (subagent return, test run, edit group). <60 lines; rewrite, don't append forever.
4. AFTER: mark `done` + how verified, commit (small; never carry uncommitted work across task boundary).
5. SUBAGENTS: pass task ID + state-file paths. They write full result to `.agent/reports/<task-id>.md`, return ≤10 lines: status, files changed, blockers.
6. Tasks idempotent: half-done must be safe to redo.
7. `.agent/scratch.md` = notes worth keeping across cut-off.
8. Never start large step before plan is on disk.

Multi-step, no `.agent/` → load `agent-state` skill. Trivial one-shots need no state.

## Context hygiene
- GitNexus-indexed repo → query GitNexus (`query`/`context`/`impact`) before opening files; name files to read.
- Filter noisy output (`| tail`, `| grep`, `--quiet`).
- Prefer task-boundary `/clear` + state files over auto-compaction. No model switch / MCP toggle mid-session (breaks prompt cache).

## Machine: Windows 11
- Bash tool = Git Bash; PowerShell 7 too. Use `python` (`python3` = MS Store stub).
- Config/hook paths: forward slashes, absolute (`C:/Users/molna/...`).

@RTK.md
