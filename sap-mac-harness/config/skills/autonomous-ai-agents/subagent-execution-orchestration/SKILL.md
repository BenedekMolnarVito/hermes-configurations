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

## Resuming across /loop wakeups (self-paced recurring execution)

When a long multi-phase plan is driven by a /loop (each wakeup is a fresh turn, often a fresh
context), treat every wakeup as a resume, not a continuation:
- Re-detect state FRESH from git + the ledger at the top of each iteration — never assume a
  prior iteration's state still holds. Run `git log --oneline`, `git status`, `git worktree list`,
  and read `<workspace>/progress.md`; the ledger's completed-phase lines + the actual commits are
  the only authority on where you are. The loop prompt itself says to re-check files/processes.
- NON-GIT, user-scoped plans (e.g. everything writes under `~/.hermes/`: config.json, hooks,
  plugins) have NO commit and NO ledger — the completion signal is the FILE ON DISK, not a sha.
  Re-detect state each wakeup by stat-ing each task's expected output path AND content-probing it
  (`python3 -c 'import json; json.load(open(p))'` for config, `python3 -c 'import m'` for a module,
  grep for the key the task was supposed to add), because a task can land a half-written file (e.g.
 plugin.yaml present but patch.py missing) that a bare directory listing reports as 'exists'. Classify per task
  from disk: fully-present+valid = done; partial/missing with a live child still `running` =
  resuming (leave it); missing with no live child = stalled (finish in controller). The three-state
  rule below holds — just read 'file present + content-valid' wherever it says 'commit'.
- Dispatch the next phase, then END THE TURN. When every remaining phase depends on the one you
  just dispatched (a serial dependency chain — scaffold → data → services → hooks → UI), there is
  NO independent IMPLEMENTATION work to fill the wait; ending the turn is the required async handoff
  so the child's result re-enters next iteration. Do not manufacture polling or no-op calls to keep
  the turn open, and do not claim the phase done before its result returns.
- BUT the wait is not empty: pre-write the NEXT phase's brief file while the current phase runs or
  is being reviewed. The next brief only needs the interfaces the just-committed phase created —
  grep the committed src for the exact exported signatures (`grep -n "export" <file>`, read the fn
  headers) and bake those verbatim into the brief so the next implementer builds on real signatures,
  not the plan's stale prose. Fold any deferred-minor from the completed phase's review into the
  brief of the phase that owns the fix (e.g. a 'enforce X in the hook' minor from the data review
  becomes an explicit step in the hooks brief). This is legitimate controller work, not a no-op.
- A /loop wakeup INTERRUPTS the live child mid-run; it resumes FRESH on the next wakeup (its
  running_seconds resets, delegate_task(action='list') still shows it `running`). So at the top of
  each iteration a dispatched phase has three distinguishable states — classify before acting, do
  NOT re-dispatch on sight of 'incomplete':
    1. COMMITTED — the phase commit is in `git log`, tree clean → verify the gate yourself, review, advance.
    2. RESUMING — action='list' shows the child still `running`, files partially present, no commit
       yet → leave it alone, read a bounded window of the live_transcript to confirm forward progress
       (reading the brief, writing files, running tests), end the turn. It will finish next iteration.
    3. STALLED/ABANDONED — no live child AND no commit AND files sit untouched → it died mid-task.
       Finish the interrupted work yourself in the controller (run the gate, fix the last red step,
       commit) rather than re-dispatching from scratch; the files it already wrote are usually correct.
  The commit, not the child's liveness, is the completion signal.
- A /loop-interrupted child that resumes next wakeup usually re-spawns at the CONTROLLER/default
  model tier, NOT the tier you dispatched it with — delegate_task(action='list') will show a phase
  you launched at `deep` now `running` as `standard`. The brief is detailed enough that the lower
  tier usually still succeeds, so do not kill+re-dispatch just to restore the tier (that spawns a
  second writer and wastes the work already done); instead scrutinize that phase's REVIEW harder for
  the judgment-heavy parts you wanted the higher tier for (e.g. a tricky integration), and only
  escalate a fix round to the higher tier if the review finds a real defect. Pick `standard` as the
  floor for any phase you expect a /loop to interrupt, since the tier won't survive the resume anyway.
- The loop ends only when the plan's Definition of Done is met and verified — emit the loop's
  stop sentinel then, not before.

## Bulky read/write/extract -> chunk-and-synthesize, don't run it directly

When a step's problem is VOLUME (a huge file read to be distilled, a many-URL
extract, a document large enough to truncate at the output limit, a scan-the-tree
sweep) rather than difficulty, do NOT run the bulky tool call in the controller
-- it floods the long-running orchestrator context. Map it across subagents that
each return a DISTILLED result to a file, then ONE synthesis agent reduces the
chunks into the whole; the controller keeps only the final artifact path. This is
enforced: the JEV `hook_bulk_io_guard.py` pre_tool_call gate HARD-BLOCKS a direct
bulky read_file/web_extract/write_file and points at the chunked-bulk-io-synthesis
skill. See that skill for the map->reduce partitioning, parallel-vs-serial rules,
and the `JEVGUARD_BULK_IO=off` bypass for a read you genuinely need verbatim.

## Working in place vs. a worktree

`git worktree add <path> <branch>` FAILS when <branch> is already the active checkout
('already used by worktree at ...'). For the SERIAL phases of a plan, just work IN PLACE on the
already-checked-out branch (commits land on the same branch either way) and reserve new worktrees
for Phase-N file-disjoint PARALLEL clusters only (see below). Record the in-place choice as a
preflight ruling so a later iteration doesn't re-attempt the failing worktree add.

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

VERIFY the tier actually took, don't trust the dispatch: on an install where the JEV delegate-route
hook (hook_delegate_route.py, a pre_tool_call hook calling decisions.complexity_tier) is active, the
hook — not your per-task `model`/`provider` pin — decides the worker tier. The pin is best-effort,
not binding (the delegation runtime can drop it), so a batch can silently collapse to one tier.
The gate is the source of truth; tune the gate rather than fighting it with pins.

ROOT CAUSE of why per-task model is dropped, and the fix that makes it binding: stock Hermes
`tools/delegate_tool.py::_build_children` resolves ONE credential bundle for the WHOLE batch
(`_resolve_delegation_credentials` from the `delegation` config section) and passes `creds["model"]`
to EVERY child — it iterates each task dict but NEVER reads `task.get("model")`/`task.get("provider")`.
So the hook injects a per-task model, the task's goal/context get modified (proving the modify
directive applied), yet every child still runs on the delegation default (standard/sonnet). The
docstring's "per-task beats top-level" refers to role/output_schema/images, NOT model. Confirm from
the ledger: all subagent rows one model regardless of the hook. The user-scoped FIX (survives
`hermes update`) is a monkey-patch plugin that wraps `_build_children` +
`_build_child_preserving_parent_tools`: stash the live task_list in a thread-local, and for each task
carrying a `model`, resolve a per-task bundle (reuse `_resolve_delegation_credentials` with the task's
model/provider overlaid on the batch routing_cfg) and substitute model + override_provider/base_url/
api_key/api_mode for THAT child. All tiers sharing one provider+base_url means only `model` changes
per task, so the overlay is always valid. Reference implementation + its test harness:
~/.hermes/plugins/delegate-pertask-model-patch/ (patch.py, test_pertask_patch.py). With it enabled,
one batch routes trivial→haiku AND deep→opus simultaneously (verified in the ledger). The routing chain,
all under ~/.hermes/agent-hooks/ and jevlib/ (stdlib-only, Python 3.9, fail-open): JEV `score()`s
each goal against the ordinal `_COMPLEXITY_LEVELS` list in jevlib/decisions.py (0.0≈band0,
1.0≈band1, 2.0≈band2); config.tier_for_score maps the score to a tier via jev-guard.json
`routing.thresholds`; the hook injects that tier's model from `routing.<tier>`.

When quick/haiku never fires (everything lands on standard), fix the CLASSIFIER, in this order:
- Thresholds sit at the BAND MIDPOINTS, not round numbers: on a 3-level ordinal scale the 0↔1
  boundary is 0.5 and the 1↔2 boundary is 1.5, so `standard_min: 0.5`, `deep_min: 1.5`. A
  `standard_min` above 0.5 (e.g. 0.6) biases borderline-trivial tasks into standard. Update BOTH
  jev-guard.json AND the DEFAULTS mirror in jevlib/config.py (the fallback) — they must match.
- SHARPEN the level descriptions (Agentic-Design-KB lesson 5-2: disambiguate fuzzy boundaries with
  explicit, mutually-exclusive criteria + concrete EXAMPLES, never a vaguer self-reported score).
  Vague one-liners make trivial tasks score mushily at low confidence; crisp bands with examples
  pull them to ~0.0-0.2 at HIGH confidence. Each band states what it is, what it is NOT, and 2-3
  example tasks. CALIBRATE empirically (KB 5-5): score representative real goals through JEV
  (jevlib.decisions.complexity_tier) and confirm trivial→<0.5, scoped→~1.0, design→≥1.5 before
  trusting the thresholds; do not guess the cutoff.
- Make the gate AUTHORITATIVE so a dropped/stale pin can't collapse the batch: the hook applies the
  JEV-classified tier even when a task already carries a model, EXCEPT never downgrade a deliberate
  higher-tier escalation pin (keep the pin only when pinned_rank > jev_rank). An env escape
  (JEVGUARD_RESPECT_PINS=1) restores the old 'fill only when empty' behavior.

After a batch finishes, read the TRUTH from the token ledger: `sqlite3 ~/.hermes/state.db` table
`session_model_usage` (cols: session_id, model, task, api_call_count, input_tokens, output_tokens,
cache_read_tokens, cache_write_tokens) joined to `sessions` (source='subagent', title LIKE
'Subagent: %', parent_session_id = your session). Group by model to see what each worker ACTUALLY
ran on — the classifier-level validation above proves the gate's intent, the ledger proves what the
runtime did; confirm haiku rows actually appear before claiming tiered routing works end-to-end.

The ledger is also the authoritative source for a per-model token report: output_tokens is fresh
generated tokens; cache_read_tokens dwarfs everything on long controller sessions (prompt-cache
replay, cheap) so report it in its own column, never summed into 'input'.

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

## Steering a live child off a wrong path (don't wait for a bad commit)

`delegate_task(action='steer')` queues a correction into a RUNNING child's next tool result
without killing it. Use it when watching the live_transcript reveals the child is thrashing — the
load-bearing signal is REPEATED patches to the SAME file chasing the SAME failure (3+ edits on one
file, each 'wait, that won't work either' in its thinking). Thrashing almost always means it is
contorting PRODUCTION code to satisfy a bad TEST rather than fixing the test. Steer it to the root:
- The classic case is a React hook test that calls a state setter AND the action that reads that
  state in ONE `act()` block, then the child mutates refs synchronously inside the setters to beat
  React's batching. That ref-in-setter hack is an anti-pattern that misleads the component consumer
  downstream. The fix is in the TEST: split into two `act()` blocks (setter in the first, the
  action awaited in the second) so React re-renders between them; keep the hook holding plain
  useState and reading state normally. Steer: 'revert the ref hack, fix the test to use two act
  blocks.'
- Keep the steer directive and specific: name the anti-pattern to revert, the correct approach, and
  the gate to re-run. The child sees it appended to its next tool result; the current tool call is
  never cut, so steer EARLY rather than letting it commit a contorted green.
- Watch dependency placement in a delegated install: a child adding a test-only peer (e.g.
  @testing-library/dom, needed by renderHook) often drops it in `dependencies` instead of
  `devDependencies`. Catch it in the steer or the review, not after merge.

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

For a plan whose task is a RUNTIME monkey-patch / hook / override into a host it does not own (e.g.
patching a plugin's class, wrapping a provider method), the final review MUST verify the patch point
actually REACHES the live object at runtime — 'the module imports and the unit test passes in bare
python' proves nothing. The classic trap: patch.py does `import <plugin>` to grab the class, but the
host loads plugins via `importlib.util.spec_from_file_location` under a SYNTHETIC module name (often
in a separate plugin-host child process), so `import <plugin>` raises ModuleNotFoundError and the
fail-open patch silently never applies — a hollow 'done'. Verdict requires reading the host's plugin
LOADER source to learn (a) the real registered module name, (b) whether register(ctx) runs in the
same interpreter where the target lives, (c) therefore whether the patch can reach it; if it cannot,
name the correct hook point (the sys.modules entry under the synthetic name, the ctx handed to
register, or the host's registry) rather than trusting the import. Fail-open is not success: a patch
that fail-opens on EVERY turn is indistinguishable from no patch — require positive evidence it fired
(a log line at INFO, a measured size drop in a FRESH session), not just absence of a crash.

TWO PREREQUISITES before a monkey-patch directory plugin loads AT ALL (both silently skip it, and a
skipped plugin looks identical to a working-but-ineffective one — check ~/.hermes/logs/agent.log for
`Failed to load plugin '<name>'` and `capability_check ... decision=deny`): (1) A directory plugin
MUST contain `__init__.py` exposing `register(ctx)` — the loader imports the PACKAGE's __init__.py and
calls its register (hermes_cli/plugins_loader.py raises `No __init__.py in <dir>` otherwise); a bare
patch.py with a module-level register() is NEVER called. Keep patch logic in patch.py and have
__init__.py `from patch import _apply_patch; _apply_patch()` inside its register. (2) `plugins.enabled`
is an ALLOWLIST (gate_manifest: `if enabled is None or not names & enabled` → skip), so the plugin
must be in it — `hermes plugins enable <name>`. (3) Replacing a core tool/function needs the
`tools.override` capability: declare `capabilities: [tools.override]` in plugin.yaml AND grant it with
`hermes plugins enable <name> --allow-tool-override` (non-interactive enable fails closed — the
capability is NOT granted without the flag or an interactive consent). Verify with `hermes plugins
capabilities <name>` showing `granted`. NEVER hand-edit config.yaml for any of this; use the CLI.
Plugins take effect on the NEXT fresh session, so verify end-to-end with `hermes chat -q` + the ledger,
not in the current session (its tool registry is already built).

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

- Re-dispatching a phase on a /loop wakeup just because it looks incomplete — the loop interrupts
  the live child mid-run and it resumes fresh next wakeup. The COMMIT (not the child's liveness) is
  the completion signal; a running child with partial files is resuming, not failed. Re-dispatching
  spawns a second writer on the same branch.
- Delegating a step that writes a protected agent-instruction file (AGENTS.md / SOUL.md) — the
  write is BLOCKED (needs the user's consent, which a subagent cannot obtain), silently stalling the
  task. Do protected-file writes in the controller yourself, or defer them; keep delegated briefs
  pointed at ordinary files (e.g. append stack notes to .github/copilot-instructions.md instead).
- Re-attempting `git worktree add` for a branch that is already the active checkout — it fails
  every time; work in place for serial phases, spin worktrees only for disjoint parallel clusters.
- On a /loop wakeup, trusting earlier-iteration state instead of re-reading git + the ledger —
  context may be fresh and commits/worktrees may have changed; re-detect before acting.
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
- Letting a thrashing child commit a contorted green instead of steering it early — when the
  live_transcript shows 3+ patches to the same file chasing the same test failure, the child is
  usually bending production code to satisfy a bad test (classic: ref-in-setter hacks to beat React
  batching in a one-`act()`-block hook test). Steer it to fix the TEST, not the code; a steer reaches
  the running child without killing it, so correct before the bad commit lands.
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
