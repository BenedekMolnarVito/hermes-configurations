---
name: bugfix-orchestrator
description: Use when bugfix needs multi-agent workflow (branch, fix).
---
# Bugfix Orchestrator Skill

## Overview
This skill defines a repeatable, semi-deterministic workflow for executing bugfixes with full multi-agent orchestration. Each subtask is delegated to a subagent with fresh context, and the **synthesis-agent skill** condenses results back to the orchestrator via a structured handoff packet.

## Workflow Stages

### Stage 1: Planning & Branch Setup
- Create feature branch from develop: `feat/bugfix/<slug>`
- Analyze the bug report and create a task dependency tree
- Identify which tasks can run in parallel

### Stage 2: Systematic Debug (Parallel where possible)
- Split suspects into file-disjoint read-only clusters (e.g. native layer / bridge-lifecycle / ingestion-persistence) and delegate one debug subagent per cluster — disjoint file sets let them run parallel with zero merge risk.
- Each subagent returns: root cause hypothesis, exact file:line evidence, fix approach. Forbid edits in debug stage.
- **MANDATORY: Invoke synthesis-agent skill** to condense findings into handoff packet

### Stage 3: Fix Implementation
- Delegate fix subagents per file/area (file-disjoint = parallel)
- Each subagent implements fix + adds/updates tests
- Run typecheck + build + unit tests after each fix batch
- **MANDATORY: Invoke synthesis-agent skill** after each fix batch

### Stage 4: Verification
- Run full test suite (vitest)
- Run build verification
- Run typecheck

### Stage 5: UI Smoke Test (Emulator + Live Device When Available)
- Delegate to android-webview-jev-testing skill subagent
- Run Maestro smoke test on emulator; when the user offers a connected phone, run the same suite live on-device as a second pass — emulator proves repeatability, live device proves OS/OEM behavior.
- Capture DOM dumps, screenshots, report.json
- **MANDATORY: Invoke synthesis-agent skill** to condense smoke test results

### Stage 6: Commit & PR
- Commit changes with Conventional Commits
- Push branch
- Open PR with summary

### Stage 7: Code Review (Fresh Context Subagent)
- Delegate code review to a NEW subagent with fresh context
- Review uses PR review standards (security, correctness, style, tests)
- The review brief must explicitly demand a re-entrancy check: every new poll / rescan / retry / flush path gets asked 'what happens when the same item is delivered twice, after any dedup window has expired' — time-window dedup is not idempotency.
- Review subagent returns: PASS or list of required fixes
- If reviewer dispatch is infra-blocked (rate limit, provider error): mark the review DEFERRED, never substitute a self-review. Salvage the partial transcript/diff and condense to a short summary. Backoff 10s, then re-dispatch a NEW reviewer subagent with the same file-based review brief + the condensed partial attached; escalate the reviewer tier once (standard→deep) if the cheap pool stays congested. Max 3 retries. If still blocked, land the verification evidence and leave the review as an explicit DEFERRED item disclosed in the PR body and final report. An orchestrator self-review is not a substitute — it lacks the fresh-context property this stage exists for, and _oneshot_spawn_budget exhaustion does not downgrade a review to inline self-review.
- **MANDATORY: Invoke synthesis-agent skill** to condense review findings

### Stage 8: Iterate Fixes from Review
- If review returns fixes, delegate fix subagents
- Re-run verification + UI smoke test
- Repeat Stage 7 until review PASS
- **MANDATORY: Invoke synthesis-agent skill** after each iteration batch

### Stage 9: Final Verification & Merge Ready
- All checks green, review PASS, UI verified
- Report final status to user

## Delegation Rules
- Each subtask -> separate subagent (delegate_task)
- Route by complexity:
  - quick: factual lookups, simple verification, mechanical edits
  - moderate: scoped coding, routine edits, ordinary analysis (DEFAULT)
  - deep: difficult reasoning, architecture, root-cause debugging
  - long-horizon-complex: sustained multi-stage, cross-system work
- **After EVERY subagent batch, invoke synthesis-agent skill** to produce handoff packet before next delegation decision
- Synthesis is mandatory; on synthesis-dispatch infra failure, retry with backoff first (same raw summaries, same quick-tier dispatch). Only for a small batch (1–2 children) may the orchestrator condense directly from verified tool output, noting the skipped synthesis in the final report. On a large batch never skip synthesis by summarizing from memory — defer the batch decision and retry the synthesis dispatch later. Condensation must never deadlock the pipeline, but it also must never silently degrade on the batches that need it most.
- Subagent contexts are ephemeral (discarded after report)
- Failed-delegation recovery: on subagent infra failure (rate limit, provider error), treat the child as DEFERRED (transient), never FAILED. Salvage and condense the partial (transcript tail/grep, git status/diff) into a short summary. Backoff 10s, then re-dispatch a NEW subagent with the same file-based brief + the condensed partial summary attached so it resumes where the previous one 429-d; escalate the tier once (quick→moderate or moderate→deep) if the cheap pool stays congested. Max 3 retries. The orchestrator absorbs spoke work inline only for a single trivial leftover that was already keep-inline — never a whole task and never a review. A still-blocked child keeps its salvaged partial attached and is disclosed as DEFERRED in the final report.
- Attribute gate failures by file ownership: typecheck/build errors in files outside `git diff --stat` are pre-existing — note them and move on, do not chase them as regressions.

## JEV-Based Decision Points
- Use jev-decisions skill for: classifying bug severity, ranking fix approaches, verifying test coverage adequacy
- Use jev-engineering for: gating PR readiness, triaging test failures

## Input Parameter
The skill accepts a `bug_description` parameter (string) describing the bug(s) to fix. Can be a list.

## Output
Final PR URL + summary of changes + verification evidence

## Lessons Learned
- When the bug is reported as a regression, first diff the subsystem between the last-known-good tag and HEAD (`git diff <tag> HEAD -- <paths>`): if the logic is unchanged, the cause is lifecycle/wiring (manifest, receivers, startup order), not code — then scope each suspect merge (`git diff <merge>^1 <merge> --stat -- <paths>`) to isolate the regressing change faster than re-reading the whole current tree.
- Independently verify a debug subagent's 'cannot compile / cannot work' claim with the real toolchain or language semantics before repeating it in PR text — e.g. Kotlin exposes Java getters as properties, so an 'unresolved member' can still compile and the true defect hides behind the wrong story.
- Any fix that (re-)polls a snapshot source — notification shade, inbox listing, queue scan — needs identity-based idempotency (stable item key, persisted across restarts), because a time-window dedup lets the same item through once it ages past the window and every re-poll then mints a duplicate.
- Always verify on-device with Maestro/CDP, not just jsdom
- Prove 'pre-existing' with `git stash` + re-run of the exact failing test, not just file ownership — unhandled-error counts and flaky tests can look related to the fix, and a clean-HEAD rerun settles it in one command.
- Share button removal must also clean up useTodos hook (shareExport) and App.tsx injection
- Export/Import buttons moving to header requires CSS flexbox rework (justifyContent: space-between)
- Tests must be updated to match new UI structure
- Code review subagent MUST have fresh context (no prior conversation contamination)
- When a prior commit removed "dead" Capacitor plugins (@capacitor/share, @capacitor/filesystem)
  that a feature actually needs, re-adding them is correct — verify the feature works, not
  whether the plugin was imported elsewhere. "Dead" means no code path uses it; if the
  feature's code path was removed alongside the plugin, restoring both is one change.
- Capacitor Filesystem Directory.DOWNLOADS fails on Android (mkdir "already exists",
  writeFile "Missing parent directory"). Fall back to `Share.share({text: content})` or
  `Directory.EXTERNAL_STORAGE` with a subdir. Unit-test the export JSON format when the
  on-device path is blocked; never fabricate on-device results.
- Write a condensed handoff doc to `docs/<feature>_HANDOFF.md` when a session is
  interrupted or ends mid-task, so the next agent can resume without context loss.