---
name: subagent-execution-orchestration
description: "Use on Hermes to run a plan via delegate_task (ops layer for superpowers:subagent-driven-development)."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [subagents, delegation, orchestration, execution, worktrees, code-review]
    related_skills: [parallel-review-subagents, change-integration-analysis]
---

# Subagent Execution Orchestration

The CONTROLLER-side operational layer for running an implementation plan task-by-task
via delegate_task: one fresh implementer subagent per task, a task review after each,
a whole-branch review at the end. The METHODOLOGY (ledger, fix-loop caps, rulings) comes
from the process skill you were told to use (e.g. superpowers:subagent-driven-development);
this skill carries the mechanics that process skills leave to you: how to parallelize a
serial plan, how to dispatch without stream timeouts, how to package reviews when the plan
doesn't use 'Task N' headings, and the integration gaps the final review must hunt.

Read this skill alongside the process skill at the START of an execution session, not mid-loop.

## When to Use

- You are the CONTROLLER executing a multi-task implementation plan by dispatching
  implementer + reviewer subagents (a subagent-driven-development / executing-plans run).
- The plan has several tasks and you want to parallelize the independent ones, or it uses
  non-'Task N' headings, or it stacks multiple tasks on shared files.
- NOT for a single delegated task, and NOT for parallel READ-ONLY review of N artifacts
  (that is parallel-review-subagents).

## Model-tier dispatch (resolve, never inherit)

Always pass the model explicitly on every delegate_task — an omitted model inherits the
controller's (often the most expensive) model, silently defeating tiered routing. Resolve the
concrete ids from config.yaml `model.aliases` (deep/standard/quick) at session start and reuse:
- quick (haiku): mechanical single-file edits with the full spec in the brief; trivial re-reviews.
- standard (sonnet): well-scoped 1-2 file changes with clear acceptance (most tasks AND most reviews).
- deep (opus): multi-file coordination, design judgment, migrations, and the final whole-branch review.
Scale the REVIEWER tier to the diff, not the task's tier: a large or high-risk diff (DB migration,
cross-cutting change) gets a deep reviewer even if the implementer was standard.

## Dispatch mechanics

- Large dispatch prompts time out the delegate_task stream. When a brief runs long (detailed
  multi-fix instructions, embedded code, long rulings), WRITE it to a file in the plan's workspace
  and send a SHORT dispatch prompt that says 'read <path> FIRST, it is authoritative' plus the
  hard guardrails (branch, no-subagents, no-merge/push, test+build gate). Keep every dispatch's
  argument text well under ~8K tokens.
- Hand artifacts over as FILES, not inline. Everything pasted into a dispatch prompt and everything
  a child prints back stays resident in the controller context for the rest of the session and is
  re-read every turn. Brief files, review packages, and reports live on disk; the dispatch and the
  child's return carry only paths + a short status.
- A dispatch describes ONE task plus the interfaces it touches and the global gate — never the
  session's accumulated history. Do not paste 'state after tasks 1-3' into later dispatches.
- Carry forward only what a later task cannot know: interfaces earlier tasks created, and your
  rulings. When task B edits files task A already changed on the same branch, tell B to READ the
  CURRENT state of those files before editing and name what it must not break (a param/signature a
  prior task added) — recon line numbers from the plan are stale after earlier tasks commit.

## Parallelizing a serial plan via file-disjoint clusters

The default is serial (never two implementers writing the same branch — guaranteed conflicts). To
parallelize safely, partition the remaining tasks into clusters by the FILES they touch:
- Build the file-touch set per task; two clusters are parallelizable IFF their file sets are
  DISJOINT (verify set-intersection is empty — do not eyeball it).
- Tasks WITHIN a cluster that share files stay serial among themselves; run the whole cluster as
  ONE multi-task subagent that commits each task separately, OR serially on one branch.
- Run each disjoint cluster on its OWN git worktree + branch, in parallel, then merge at the end.
  A file-disjoint merge is conflict-free by construction; confirm with the merge's conflict count.
- Honor hard intra-cluster ordering (task B depends on task A's new value/type → A before B) and
  record it; a dependency edge inside a cluster forbids reordering even though files overlap.
See references/worktree-cluster-parallelism.md for the worktree setup, deps-install, and
scratch-file-leak guard.

## Review packaging when the plan uses non-'Task N' headings

The process skill's review-package / task-brief scripts match on 'Task N' headings. Plans that use
'FR1'/'FR2'/section names make those scripts return 'task N not found'. Fall back to generating
packages by hand: split the plan into per-task brief files once up front, and build each review
package as `{ commit list; diff --stat; diff -U8/-U10 } > <task>-review-package.md` over the
task's BASE..HEAD. BASE is the commit recorded BEFORE dispatching that task's implementer, never
HEAD~1 (which drops all but the last commit of a multi-commit task). Dump the full diff to the file
and hand the reviewer the PATH; never inline a multi-hundred-line diff into the review dispatch.

## Reading a child's result without the full transcript in context

Results deliver between turns as batch-completion messages; the controller must not poll. But the
batch message's stored summary is often TRUNCATED (large verdicts show '(+N chars)'). To get a
verdict's specifics without re-reading the whole transcript into context, grep the live_transcript
for the verdict markers (SPEC:/PASS/FAIL/Important/Minor/ADDRESSED) and read a bounded window around
them. Verify every claimed commit yourself (`git show --stat <sha>`, tree clean, scope correct, NO
files from another cluster leaked) before accepting a child's 'DONE'.

## The final whole-branch review hunts cross-task integration gaps

Per-task reviews are task-scoped and structurally CANNOT see cross-task gaps. The final review's job
is exactly those. The highest-value class, seen repeatedly: an EARLIER task defines a persisted
field/column/interface, and a LATER (or earlier-but-adjacent) task that serializes/round-trips data
never learns about it — so export/import, copy, or sync silently drops the new field. Give the final
reviewer the full branch diff + every per-task brief and point it explicitly at the shared files two
clusters both touched, at round-trip paths (export/import, serialize/deserialize), and at
regression/consistency. A gap like this is load-bearing (a feature silently loses state) → fix before
merge in ONE fix wave + ONE scoped re-review, not a per-finding loop.

## Transient child failure — DEFERRED, never FAILED, never absorbed

A child that fails with rate-limit / 429 / provider error / insufficient-credits is transient infra, not a verdict on the task. The controller must NOT do the child's work inline as fallback (that burns controller context and — for reviewers — destroys the fresh-context property the review depends on), and must NOT discard a long session's partial output.

- **Classify:** mark the child DEFERRED, record the error class + which tier/pool was congested.
- **Salvage + condense:** `delegate_task(action='stop')` still returns the partial result; grep its `live_transcript` for verdict markers; run `git status` / `git diff --stat` for surviving edits; keep scratch brief/report files. Condense the salvage to a short summary.
- **Recover in order:** backoff **10s**, re-dispatch a NEW subagent with the same file-based brief + the condensed partial summary attached so it resumes where the prior one 429-d; escalate the tier once (quick→moderate or moderate→deep) if the cheap pool stays congested. **Max 3 retries.**
- **Inline absorption is allowed only for a single trivial leftover that was already keep-inline — never a whole task and never a review.** `_oneshot_spawn_budget` exhaustion does NOT downgrade review/verification to inline self-review: mark DEFERRED and re-dispatch.
- **Disclose:** a still-blocked task ships as an explicit DEFERRED item with its salvaged evidence, never as a silent self-done.

## Verification gate (every task, every fix)

A pre-existing baseline test failure is NOT yours to fix and NOT a reason to block — but record its
exact identity (test name/file) at session start and assert that identity each run, so a REAL
regression can't hide behind the known-failing count. 'N pass + 1 known failure' is the bar; 'N pass
+ 1 failure' with a DIFFERENT failing test is a regression. Confirm the failing test is the SAME one,
not just the same count. Run the full suite + build yourself on the merged branch before the final
review and before presenting integration options.

When several implementers run in parallel and each ends by running the WHOLE suite, their reported
test COUNTS will disagree (e.g. 76 / 66 / 76) — each child's final run saw a different subset of its
siblings' still-being-written test files. That divergence is a harmless race artifact, NOT a failure
or a missing-tests signal. Ignore the children's counts entirely; the only authoritative count is the
controller's own full-suite run after ALL parallel children have landed.

## Finish

After the final review is clean (and its fix wave re-reviewed), clean up every parallel worktree
(`git worktree remove --force <path> && git worktree prune`) and delete merged cluster branches
(`git branch -d`). Then present the integration menu (merge locally / push+PR / keep) and WAIT —
merging to a shared base or pushing is the user's decision. Collect every ruling you made into the
final report so the user can rework any you got wrong.

## Pitfalls

- Omitting the model on a dispatch inherits the controller model — always pass it explicitly.
- Inlining a long brief or a big diff into the dispatch prompt times out the stream and bloats
  context; write to a file, pass the path.
- Trusting the plan's recon line numbers after earlier tasks committed — they drift; tell the
  implementer to read current file state.
- Eyeballing 'these tasks look independent' instead of verifying disjoint file sets before
  parallelizing — a shared file across two live branches is a merge conflict waiting to happen.
- Accepting a child's 'DONE' / 'tests pass' without verifying the commit and re-running the gate
  yourself; a child's report is a self-claim, not a verified fact.
- Trusting a child's 'files created' when the file-mutation verifier flagged a FAILED write, or on a
  NON-git target where you cannot `git show` -- a child can land a file at a TYPO'd/wrong path, self-
  correct on a retry, and still report DONE with a passing suite, so the self-report alone can't tell
  you what actually landed. Verify on disk directly: stat the exact expected path (size + mtime), run
  the suite yourself, and AST/grep the file to confirm it holds the real implementation, not a stub.
- Confirming a function is DEFINED is not confirming it is CORRECT: an AST check that only asserts the
  `def` exists will pass a function that is missing its `return` (falls through to None) or returns a
  stub — a latent bug a later task's TDD then eats time rediscovering. When you verify a pure helper on
  disk, assert it has a non-None return on each branch (count `ast.Return` nodes with a value), not just
  that the name is present.
- Letting the known baseline failure mask a regression by checking only the pass COUNT, not the
  failing test's identity.
- Assuming a Hermes-spawned hook/skill subprocess inherits the agent's environment: `hermes chat -q`,
  `hermes hooks test`, and the gateway spawn hook/script subprocesses WITHOUT the keys from
  ~/.hermes/.env, so a delegated helper that reads an API key straight from os.environ silently fails
  open (empty verdict) even though the key is in .env. Fix at the DEPLOYMENT layer, not the library: a
  tiny envload helper that loads ~/.hermes/.env into os.environ for ABSENT keys, called at the top of
  each hook/script — keep the core library pure (os.environ only) so its fail-open tests still hold.
  When adding such a fallback, any test that asserts fail-open-on-no-key must point HERMES_HOME at a
  keyless temp dir, or the fallback will load the real .env and the no-key assertion breaks.
