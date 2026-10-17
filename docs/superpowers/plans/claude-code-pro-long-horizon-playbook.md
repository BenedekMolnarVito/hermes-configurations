# Claude Code (Pro) Long-Horizon Playbook

Stretching the 5-hour window and surviving it when it runs out.
Written 2026-10-17. Based on web research; third-party claims are marked. Verify anything marked **(verify)** against current docs for your CLI version.

---

## 0. TL;DR

1. **Resumability is the foundation.** Every session must be able to die at any moment and be picked up by a fresh context. State lives on disk, never in the conversation.
2. **A resumer is mandatory** for unattended work: something must wake the session after the limit lifts.
3. **The agent must always be told about this** via a mandatory block in the global `CLAUDE.md` (section 2.2) plus a `SessionStart` hook that injects the progress file.
4. **Spend Pro quota only on planning and review.** Push bulk execution to cheaper models (including your LiteLLM/Zen path, which does not touch the Pro window).
5. **Cut input noise first** (tool output, MCP overhead, bloated context). Output-style tricks like Caveman are a minor lever.
6. **Measure.** Baseline with `/usage`, `/context`, and `ccusage` before and after every change.

---

## 1. Verify first

| Check | Why |
|---|---|
| `/model`, `/usage` | Sources disagree on whether Pro gets Opus in Claude Code. Do not design around an Opus orchestrator until confirmed. |
| No `ANTHROPIC_API_KEY` in your env | If set, Claude Code uses it instead of the subscription. |
| Avoid `claude -p` (headless) for burning subscription quota | One third-party pricing guide reports that since 2026-06-15 headless/automated use draws from a separate monthly credit pool ($20 on Pro). **(verify on Anthropic's support pages)** |
| Weekly cap | Pro also has a weekly limit. Draining every 5-hour window will hit it. Watch the weekly percentage in `/usage`. |

---

## 2. Rate-limit-proof workflow (the core)

### 2.1 State files

Per project (single repo) use `.agent/` in the repo, kept out of git via `.git/info/exclude`.
For multi-repo work use **one central directory** outside all repos, e.g. `~/agent-work/<project>/`, so the orchestrator has a single source of truth.

```
.agent/
  PROGRESS.md        # Now / Next / Blockers / Decisions. Hard cap ~60 lines.
  TASKS.md           # Task list with status + verification step per task
  scratch.md         # Hypotheses, useful command output, notes. Trim regularly.
  INTERRUPTIONS.md   # Appended by the rate-limit hook (timestamps)
  reports/<task-id>.md   # Subagent results, one file per task
```

### 2.2 Mandatory block for the global `~/.claude/CLAUDE.md`

Copy this verbatim. Keep it short so it does not bloat every turn.

```markdown
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
```

### 2.3 `TASKS.md` template

```markdown
# Tasks: <project>
Updated: <ISO timestamp>

| ID | Status | Repo | Description | Verify by |
|----|--------|------|-------------|-----------|
| T1 | done | api | Add token refresh endpoint | `pytest tests/auth` green |
| T2 | in-progress (2026-10-17T14:02) | web | Wire refresh into client | `npm test`, manual login |
| T3 | todo | android | Handle 401 + retry | emulator login flow |

Statuses: todo | in-progress | blocked | done
```

### 2.4 `PROGRESS.md` template

```markdown
# Progress (max ~60 lines)
## Now
T2: wiring refresh into web client; interceptor written, tests not yet run.
## Next
T3 android retry; then T4 docs.
## Blockers
none
## Decisions (why, not what)
- Refresh tokens rotate on use (T1); client must store the new one.
```

### 2.5 Hooks (settings.json sketch, **verify event names with `/hooks` on your version**)

A `StopFailure` event with a `rate_limit` matcher exists per community tooling. Use it only to leave a trace; the resumer does the waking.

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command",
        "command": "head -n 80 .agent/PROGRESS.md 2>/dev/null || true" } ] }
    ],
    "StopFailure": [
      { "matcher": "rate_limit",
        "hooks": [ { "type": "command",
          "command": "mkdir -p .agent && echo \"- $(date -Is) RATE LIMIT HIT. Resume from Now/Next in PROGRESS.md\" >> .agent/INTERRUPTIONS.md" } ] }
    ]
  }
}
```

The `SessionStart` hook is a deliberate exception to "avoid auto-injected memory": the file is tiny, capped, and essential.

### 2.6 The resumer (headed mode, no wrapper daemon)

Install community plugins through `/plugin`. Review the code before installing; these are third-party.

| Tool | What it does (per its own description) |
|---|---|
| **resumer** | Resumes only Claude Code sessions interrupted by rate limits; its hooks bind the session at start, schedule a resume on a matching `StopFailure`, and clear the binding at session end. It is a recovery tool, not a token compressor. |
| **TaskWake** | Records the interrupted session and resumes the exact transcript in a new visible terminal. Has a headless fallback: **disable it** (see section 1). |
| Others (claude-auto-retry, unsnooze) | Exist; not reviewed here. |

Operational rules:

- Run Claude Code inside **tmux on the always-on Ubuntu server**, so the session survives disconnects.
- **Cold cache after a long wait.** Prompt cache TTL is about 5 minutes (per one source), so a resume re-reads the whole transcript at full price. This is the main reason state files matter more than conversation history.
- **Reduce recovery waste:** let the resumer wait for a rate-limit recovery instead of repeatedly retrying by hand. Keep PROGRESS.md and TASKS.md concise and current so resumed work can continue from verified state rather than re-derive decisions or redo completed tasks. The resumer itself does not reduce prompt tokens.
- **Manual fallback** if the resumer fails: `claude --continue` (or `claude --resume`), then paste:

```
Resume per the persistence protocol. Read .agent/PROGRESS.md and TASKS.md,
verify git state in every repo, then continue with the first unfinished task.
```

- Test the resumer on your first real limit hit and keep an eye on it; you cannot force a limit on demand.

### 2.7 Multi-repo orchestration resume protocol

Put this in your orchestration skill:

1. Orchestrator state lives in `~/agent-work/<project>/` (PROGRESS.md, TASKS.md, `reports/`). TASKS.md has a `Repo` column.
2. Launch with `claude --add-dir <repoA> --add-dir <repoB>` so one session sees all repos.
3. On startup the orchestrator reads state, then runs `git status` plus `git log -5` per repo, and reconciles any mismatch (e.g. a task marked `in-progress` whose commit already exists becomes `done` after verification).
4. Use one git worktree per repo or task for parallel subagents, so a cut-off cannot leave a shared tree half-edited.
5. Each subagent writes its report file *before* returning. If the session dies mid-run, the report on disk is the recovery point.

---

## 3. Model routing

- **`/model opusplan`**: Opus plans, a cheaper model executes. Called the best compromise for most cases by one guide. **(verify availability on Pro)**
- **`CLAUDE_CODE_SUBAGENT_MODEL`** sets one cheap default for all subagents; per-agent `model:` frontmatter overrides it.
- **Lower the effort level** for easy tasks; thinking tokens are billed as output.
- **Hybrid with your existing stack (biggest lever):** use the Pro window for planning and review only, write the plan to files, then run bulk implementation in OpenCode/OMO on the Zen open-weight models, or in a second Claude Code profile (`CLAUDE_CONFIG_DIR`) pointed at LiteLLM. Those tokens do not count against Pro. Hand off through `TASKS.md`, not chat.

---

## 4. Cut input noise

- **Filter tool output** before the model sees it. RTK installs a PreToolUse hook that rewrites noisy Bash commands (`rtk init --global`).
- **Cap output:** `CLAUDE_CODE_MAX_OUTPUT_TOKENS` (soft cap).
- **MCP overhead:** tool search defers MCP schemas by default; one measurement found the `auto:5` threshold mode loaded everything anyway. Confirm with `/context`.
- **Code graph first:** add a CLAUDE.md rule to query GitNexus before reading files.
- **Plan before code** (Ctrl+G to edit the plan) and name the files to read in prompts.
- **Trim answer verbosity with Caveman:** use its `/caveman` mode (or ask for a brief answer) to answer first and remove ceremony or repeated context. Keep technical facts, negations, safety warnings, code, commands, paths, and errors exact. The mode persists until turned off, so use it only when concise chat responses are useful; do not compress durable artifacts or technical payloads.

---

## 5. Context lifecycle

- Prefer a **task-boundary `/clear`** plus the state files over relying on auto-compaction.
- Compaction knobs if you use it: `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW`. Earlier compaction means smaller re-reads, but each compaction costs a summarization call.
- **Protect the cache:** do not edit CLAUDE.md, toggle MCP servers, or switch models mid-session.

---

## 6. Subagents

- Each subagent reloads system prompt, CLAUDE.md, and tool definitions, so every spawn has a fixed cost. Use them for noisy exploration, not small edits.
- Enforce the return contract from 2.2 (max 10 lines, details in `reports/`).
- Keep agent definitions short.

---

## 7. Memory

| Layer | Tool | Use for |
|---|---|---|
| Durable project knowledge | **OKF bundle** (markdown + YAML frontmatter, in git, `okf index`/`okf search`; okf-gem plugin or okf-retrieve over MCP) | Decisions, playbooks, "why" notes, reviewed in PRs |
| Episodic / cross-session | **Hindsight** (MIT, retain/recall/reflect, MCP per bank) *or* your existing MemPalace | What the agent learned over time, research notes |
| Resume state | `.agent/` files from section 2 | Short-lived task state |

Guidance (my judgment, not measured):

- Do not stack three memory systems. Trial Hindsight against what you have on about 10 real tasks. Its published benchmark (39% to 83.6% on LongMemEval/LoCoMo) is the authors' own and conversational, not coding.
- Point Hindsight's extraction/reflection LLM at a cheap or local model so it does not spend Pro quota.
- Prefer recall on demand (MCP) over auto-injecting at every prompt.
- Consolidate periodically with a cheap-model pass: merge duplicates, date entries, retire stale ones. OKF's own maintainers flag "who wrote this, who checked it, is it current" as the open problem for agent-written knowledge.

---

## 8. Academic research

Untested recipe: extract each paper once with a cheap model into atomic notes (claim, evidence, citation), store them in the memory layer, and have the main agent read notes instead of PDFs.

---

## 9. Measure

- Baseline one representative task: record `/usage` before and after.
- `npx ccusage blocks` for per-window consumption.
- `/context` to see what fills the window.
- Change one thing at a time. The Caveman listing claims roughly 75% token reduction for its targeted output, but that is not a whole-session guarantee; whole-session savings may be only a few percent. Treat both as claims to measure on your own workload, and reject any compression that loses correctness or necessary context.

---

## 10. Rollout order

1. State files + mandatory CLAUDE.md block + `SessionStart` hook (section 2).
2. Install and test a resumer in tmux.
3. Output-filter hooks and code-graph-first rule.
4. `opusplan` and `CLAUDE_CODE_SUBAGENT_MODEL`.
5. Move bulk execution to the Zen/LiteLLM path.
6. OKF bundle.
7. Trial Hindsight.

---

## Sources (third-party unless noted)

- Claude Code usage limits guides: morphllm.com/claude-code-usage-limits, fast.io/resources/claude-code-pricing-guide
- Resumers: github.com/Mira190/TaskWake, [resumer skill](https://skillselion.com/skills/wong2/claude-plugins/plugins/resumer), [resumer plugin source](https://github.com/wong2/claude-plugins/tree/main/plugins/resumer)
- Token reduction: tech.autoscout24.com (RTK, output caps), composio.dev/blog/ways-to-cut-token-consumption-in-claude-code, kdnuggets.com/7-practical-ways-to-reduce-claude-code-token-usage
- Concise agent replies: [Caveman skill](https://skillselion.com/skills/juliusbrussee/caveman), [Caveman source and benchmarks](https://github.com/JuliusBrussee/caveman)
- Tool search: dev.to/rulestack/tool-search-hid-40170-tokens-from-our-first-request-auto5-put-them-all-back-2jin
- Compaction: github.com/xsyetopz/claudetto/wiki/Compaction-And-Context
- OKF: pypi.org/project/okf-retrieve, github.com/serradura/okf, github.com/kage-core/Kage
- Hindsight: arxiv.org/abs/2512.12818, hindsight.vectorize.io
