---
name: agent-state
description: Create or repair the on-disk resume state (.agent/PROGRESS.md, TASKS.md, scratch.md, reports/) that the persistence protocol requires, so work survives rate-limit cut-offs and fresh contexts. Use when starting any multi-step task in a repo (or multi-repo project) that has no .agent/ yet.
---

# Agent state

One repo → `<repo>/.agent/`. Multi-repo → `~/agent-work/<project>/` (set `AGENT_STATE_DIR` so SessionStart hook finds it).

## Create (idempotent, never overwrite)
```bash
S=.agent   # or ~/agent-work/<project>
mkdir -p "$S/reports" "$S/briefs"
for f in PROGRESS.md TASKS.md scratch.md; do
  [ -f "$S/$f" ] || cp ~/.claude/skills/agent-state/templates/$f "$S/$f"
done
# keep it out of git without touching .gitignore
git rev-parse --git-dir >/dev/null 2>&1 && { grep -qx '.agent/' "$(git rev-parse --git-dir)/info/exclude" || echo '.agent/' >> "$(git rev-parse --git-dir)/info/exclude"; }
```
Then fill TASKS.md (row per task, each with **Verify by**) + PROGRESS.md before first task.

## Rules
- PROGRESS.md ≤60 lines: rewrite Now/Next/Blockers; Decisions = "why" only.
- TASKS.md statuses: `todo | in-progress (<ISO time>) | blocked | done`.
- `INTERRUPTIONS.md` appended by rate-limit hook. Read on resume, don't edit.
- `scratch.md`: hypotheses, useful output. Trim on task close.
- `reports/<task-id>.md`: subagent results. `briefs/<task-id>.md`: long briefs.
- All state files caveman-terse; paths/commands/errors exact.
