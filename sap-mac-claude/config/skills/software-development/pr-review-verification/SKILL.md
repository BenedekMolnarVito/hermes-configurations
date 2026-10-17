---
name: pr-review-verification
description: "Use when verifying a PR's own claims during review."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Code-Review, Pull-Requests, Git, Verification, TypeScript]
    related_skills: [github-code-review, change-integration-analysis]
---

# PR Review Verification

## When to Use

- Reviewing a PR whose description makes claims you must confirm: "the failing test is pre-existing", "build is clean", "no regressions", "every feature has tests".
- The repo's `build` may not type-check, so "type-safe" needs an independent `tsc --noEmit` pass.
- The PR lives on a GitHub host your `gh` is not authenticated to.
- A diff hunk looks like a boundary/comparison bug and you want to prove it before writing it up.
- You are asked to verify SOMEONE ELSE'S review comments (inline review claims, not just the PR body) — confirm each claimed bug by running the reviewer's own reproduction against the real code before you endorse the verdict.

Not a substitute for github-code-review (fetch/diff/post/approve mechanics) or change-integration-analysis (planned-vs-branch overlap, not quality).

Makes a PR review evidence-backed instead of description-trusting. The github-code-review skill covers the mechanics (fetch, diff, post inline comments, approve/request-changes); THIS skill covers the step most reviews skip: independently proving or disproving the PR's own claims ("this failure is pre-existing", "build is clean", "no regressions") and catching the bug classes a diff-read alone misses.

Standing rule for this user: do not restate the PR author's claims as findings. Every claim in the PR body ("the one failing test is a pre-existing bug on the base branch", "build is clean", "every FR has tests") is a hypothesis to confirm against the base branch, not a fact. Report what YOUR execution returned, and name any claim you could not verify.

## Procedure

### 1. Check out the PR and run the gates the author claims pass

1. Fetch and check out: `git fetch origin pull/<N>/head:pr-<N> && git checkout pr-<N>`. node_modules usually already present on a sibling branch of the same repo; only `npm ci` if the lockfile changed.
2. Before adding a regression test, inspect the runner config (`vitest.config.*`, Jest config, pytest config) and place the file under its actual include glob. A correctly written test outside discovery proves nothing and wastes a run on “No test files found.”
3. Run the suite and build the author says are green (e.g. `npm run test`, `npm run build`). Record exact pass/fail counts.
4. Know what the build actually gates. `build` = `vite build` (esbuild) does NOT type-check — a PR can build clean and still carry TypeScript errors. If the author claims type-safety, run `npx tsc --noEmit` separately (see step 3).

### 2. Confirm a "pre-existing failure" against the BASE branch before accepting it

When the author blames a failing test on a pre-existing base-branch bug:
1. Verify the failing test is UNCHANGED by the PR: `git diff <base>...pr-<N> -- <test file>` and confirm the assertion lines show as context (unchanged), not `+` additions. A failing test the PR itself added is a different problem.
2. Run that one test on the base branch: `git checkout <base> && npx vitest run <file> -t "<test name>"`. If it fails identically there, the claim holds. If it passes on base, the PR introduced the failure.
3. Prefer a detached temporary worktree at the exact base SHA when the review checkout has uncommitted work: `git worktree add --detach <scratch-dir> <base-sha>`, run the identical focused command there, then `git worktree remove --force <scratch-dir>`. Reuse dependencies only when safe (for example, symlink `node_modules` when the lockfile is identical). This proves whether the failure exists on base without stashing, switching, or risking the active patch. If a worktree is impractical, stash/restore cleanly around branch switches.

### 3. Isolate NEW errors by diffing tool output between base and head

"No new type errors / lint errors" is only meaningful relative to the base. A project whose base already has N tsc errors makes raw head output useless — diff the two sorted outputs:
```
npx tsc --noEmit 2>&1 | sort > /tmp/tsc_head.txt
git stash -u; git checkout <base> && npx tsc --noEmit 2>&1 | sort > /tmp/tsc_base.txt
git checkout pr-<N>; git stash pop
comm -23 /tmp/tsc_head.txt /tmp/tsc_base.txt   # lines in head but NOT base
```
Normalize away `line:col` before comparing, or `comm` reports false positives. A PR that adds code ABOVE an existing error shifts that error's line number, so the identical error appears in head-not-base AND base-not-head and `comm -23` flags it as "introduced" when it is pre-existing. Strip the location first:
```
sed -E 's/\([0-9]+,[0-9]+\)//' /tmp/tsc_head.txt | sort -u > /tmp/head_norm.txt
sed -E 's/\([0-9]+,[0-9]+\)//' /tmp/tsc_base.txt | sort -u > /tmp/base_norm.txt
comm -23 /tmp/head_norm.txt /tmp/base_norm.txt   # empty => zero introduced
```
If raw `comm` shows N head-not-base lines, always check the reverse (`comm -13`): the same count of base-not-head lines at shifted positions means it is line drift, not a regression. The same base-vs-head diff pattern isolates new lint warnings or new test failures. Report only the introduced set.

Common TS regression this surfaces: a PR adds a REQUIRED field to a shared model/interface but misses object-literal call sites that build that type without going through the factory/`createX` helper. Those sites compile under esbuild and are runtime-safe only by coincidence (`undefined ? 1 : 0 -> 0`); grep for every place the type is constructed, not just the ones the diff touched.

### 4. Prove suspected bugs with a minimal probe, don't just assert them

When a diff looks wrong, confirm with a one-liner before writing it up as a finding. Example that recurs: a date-only bound compared against a datetime column.
- `endDate = "2026-09-30"` compared to a stored ISO timestamp `"2026-09-30T14:30:00.000Z"` via `col <= endDate`: string comparison makes `"...T14:30..." <= "2026-09-30"` FALSE, so every row on the last day is silently dropped.
- Probe: `node -e 'console.log("2026-09-30T14:30:00.000Z" <= "2026-09-30")'` -> `false`. Fix is an exclusive next-day bound (`< startOfNextDay`) or appending `T23:59:59.999Z`.
- Avoid apostrophes inside a `node -e '...'` single-quoted string; the shell breaks the quoting. Put the probe in a file or use double-quote escaping.

Another string-compare variant: a deadline stored LOCAL-no-Z no-seconds (`"2026-10-05T17:00"`, straight from a `date`+`time` field concat) compared against `now = new Date().toISOString()` (UTC-Z with seconds+ms, `"2026-10-05T15:30:00.000Z"`). `deadline <= now` is lexicographic over mismatched formats: under a +N offset a past-due local time can sort GREATER than the UTC now and never fire. Probe both the offset case and the prefix case (`"T15:30" <= "T15:30:00.000Z"` is `true` because the shorter string is a prefix). Fix: compare like-for-like — derive `now` in the same local-no-Z shape, or parse both to epoch.

Check whether a test would have caught the bug: read the fixture timestamps. A boundary bug slips through when fixtures use mid-period values (day 15) and never the edge (last day, today). Flag the missing boundary test alongside the bug.

### 4c. A "pre-existing / inherited" bug claim in a port or rewrite must be verified against the ORIGINAL source, not accepted

When a rewrite/port PR labels a bug "pre-existing" or "inherited from the old implementation" and lists it as an accepted follow-up, do not take the label at face value — a port can silently change an operation's SEMANTICS while looking like a faithful 1:1 port. Pull the original file from the base branch (`git show <base>:<old-path>` or grep the pre-rewrite tree) and read the actual operation.
- Recurring case: the original compared typed values chronologically (e.g. C# `DateTime a <= DateTime.Now`, local-vs-local); the port reimplemented it as a STRING compare of differently-formatted ISO strings. The original was correct; the port introduced the bug. That makes it a regression the PR introduced, not an inherited one — report it as such and tell the author to correct the "pre-existing" wording (or fix it in the PR).
- The general rule: "inherited" is a claim about the OLD code's behavior. Confirm the old code actually had the behavior before you accept the label; the right comparison is port-vs-original, same as a "pre-existing failure" is confirmed base-vs-head.

### 4b. A test that fails only under YOUR timezone is a test bug, not a code bug

Before reporting a date/time test failure as a regression, decide whether the TEST is tz-fragile. A `datetime-local` input holds a wall-clock value with no timezone; the component typically stores UTC via `new Date(local).toISOString()`. A test that enters `"2024-06-20T08:45"` and asserts the stored string `.toContain("08:45")` only passes when the runner's TZ is UTC (CI) — it fails under a non-UTC local TZ (CEST stores `06:45Z`). This is the usual root of a "pre-existing failure" on a tz-offset machine.
- Confirm it is tz-dependent, not real: run the one test under both timezones. `TZ=UTC npx vitest run <file> -t "<name>"` passes, `TZ=Europe/Budapest ...` fails => the test, not the code, is wrong.
- Fix the test to be tz-independent: assert against the component's own conversion, not a hardcoded literal — `const expected = new Date("2024-06-20T08:45").toISOString(); expect(saved.receivedAt).toBe(expected)`. This tests the real round-trip contract in any timezone.
- This is a legitimate in-review fix: a tz-fragile test is noise that masks real failures. Fix+push it, verify green under both `TZ=UTC` and the local TZ, and note it in the review rather than rubber-stamping the author's "pre-existing" claim.

### 4d. Verifying another reviewer's inline comments: run their reproduction, don't reason about it

When the task is "verify the review comments on PR <N>" (confirming claims a human reviewer already wrote, each with a reproduction and a severity like M1/M2):
1. Fetch the inline comments, not just the PR body: `gh api repos/<owner>/<repo>/pulls/<N>/comments --paginate`. Each carries `path`, `line`, `commit_id`, `in_reply_to_id`, and `body`. Confirm your checkout is AT the `commit_id` the comments were written against (`git log -1 --oneline`) — a claim is only reproducible against the code it was made on.
2. For a claim that ships a reproduction (`feed("...") -> "..."`, a forbidden-form table), RUN it against the real module and compare output to the claim. A claim backed by matching live output is CONFIRMED; a diff-read agreeing with the prose is not verification.
3. For a structural/control-flow claim (ordering, missing try/except, "only flushed at end-of-stream"), prove it from the source: grep for the single call site, read the enclosing control flow, and demonstrate the mechanic in isolation (e.g. show the stream helper holds a tail back until finish()). State it as verified-from-source, citing `path:line`.
4. Separate the reviewer's observations, impact claim, severity, and fix direction. A reproduction may confirm the mechanism while the proposed remediation is still unsafe or belongs in another repository.
5. For structured output rendered by another component or repository, trace the entire boundary before judging user-visible impact: producer payload → transport schema → renderer/formatter. Probe the producer to establish what crosses the wire, then inspect or execute the renderer to establish what the user sees. A backend pass-through is not itself a display defect when the frontend intentionally owns formatting; conversely, backend tests can all pass while the renderer still violates the shared presentation contract.
6. Validate the proposed fix against the wire contract. Preserve raw typed values when downstream sorting, charting, totals, or locale formatting depends on them; prefer fixing the display owner over recursively rewriting arbitrary payload strings, which can corrupt labels, keys, titles, and metadata. If preformatted display strings are supported, normalize only fields explicitly identified as display cells and test them separately.
7. Enumerate every renderer that exposes the same value before declaring the display fix complete: table cells, chart tooltips, axes/data labels, totals, and copied/exported text may use different helpers. Test the canonical typed-value path and the exact malformed/preformatted value from the reproduction separately; fixing only one can leave the reported user-visible escape intact elsewhere.
8. Give a per-claim verdict (CONFIRMED / partially correct / wrong), then an overall soundness read. State separately whether the evidence supports the reported severity and fix direction. Do not restate the reviewer's prose as your finding — your finding is what YOUR execution returned.
9. A verdict needs a fourth bucket beyond CONFIRMED / partially-correct / wrong: ALREADY-RESOLVED. A bot or earlier-round comment is written against a specific `commit_id`; HEAD may already carry a later commit that fixed it. Before implementing anything, grep HEAD for the exact artifact the comment names (the old GUID, the custom-tool name, the stale line) — if HEAD already shows the fixed value and the named entity does not exist, the claim is a stale/false-positive, not an action item. Report it as "already resolved in <sha>" with the HEAD evidence, and change nothing. Bots routinely assert a custom tool / field exists that never did (false positive); confirm existence in HEAD, do not take the bot's word.

### 4e. When the task is verify AND address: split by who owns the decision, never fix spec'd behavior unilaterally

When asked to "verify the review and implement the fixes" (not just report), triage every confirmed claim into two buckets BEFORE touching code, and when the split is non-obvious confirm it with the user — what gets committed depends on it:
- IMPLEMENT NOW: objective, mechanically-verifiable code defects with a self-contained fix — wrong boundary/cutover, a formatter emitting a false sign, a vacuous test, an axis that clips. You can prove the fix correct with a probe and a unit test.
- DO NOT CHANGE — human/product/backend decision: any item the reviewer themselves flags "human decision required", anything that would alter behavior a spec/AC literally specifies, and anything whose correctness depends on a fact you cannot verify from the repo (a lockstep backend deploy, whether another producer emits a given wire form, backend string conventions). Changing spec'd behavior or guessing a cross-service contract is not a review fix; it is a new decision that is the author's to make. Document these in the PR comment with the evidence and the decision needed, and implement nothing for them.
- A reviewer-labelled BLOCKER is not automatically something you implement. Severity is about impact; ownership is about who may decide. A blocker can be "documented, left for the author" when its resolution is a product/backend call.

Verify a reviewer's ROOT-CAUSE ATTRIBUTION before you accept it, especially a named cross-service dependency ("must deploy lockstep with backend PR #X", "depends on the other repo's convention"). When you can reach that other repo, open it and confirm the attribution instead of documenting it as an unverifiable risk — a reviewer can misattribute the cause. Recurring case: a reviewer blamed a frontend percent-rendering bug on lockstep with a named backend PR, but reading that PR showed it was a prose normalizer that explicitly left the machine-readable payload byte-exact; the real cause was an inconsistent value convention between two sibling prompt/skill files in the backend (one multiplied by 100, one did not). The item stays "owned by the other repo" (don't fix spec'd/foreign behavior in THIS PR), but the correct write-up names the real producer and the real one-line fix, and the fix is raised as a separate change in the repo that owns it — not left as a vague lockstep caveat. When two producers are supposed to emit the same wire convention, grep both and diff their formulas; the bug is usually that they disagree, not that a deploy is mistimed.

For a confirmed-but-unfixed misbehavior (e.g. the spec'd mixed-magnitude value crush), do not leave it silently green: add a test that PINS the current output (`toContain("€0.01bn")`) with a comment naming it as the documented open item. The suite then makes the misbehavior observable and prevents a later silent change, without you pre-empting the product decision.

A new verification test added for one review item can surface PRE-EXISTING breakage outside the PR's scope (e.g. a repo-wide registry-load test fails on unrelated already-broken files). Do not expand the PR to fix unrelated items, and do not commit a red test. Scope the new test to the PR's blast radius (the specific files/product this PR touches), and FLAG the unrelated finding in the PR comment with the evidence (which files, what fails, the silent-failure mechanism) — this user prefers flagging in the PR comment over filing a separate ticket. When the scope split is non-obvious, confirm it with the user before narrowing. Note in the test's docstring that the narrow scope is deliberate and a broader glob is a follow-up, so the next reader does not "helpfully" widen it back into red.

After fixing a boundary/cutover, grep the whole test tree for other assertions that encoded the OLD boundary — a formatter change ripples into sibling suites (payload/table/copy tests) that hard-code the previous rendering. Update those expectations in the same commit and re-run the full unit suite, or an unrelated-looking shard goes red. Separately re-confirm any pre-existing base-branch failure is still pre-existing (stash + run on base) so you don't get blamed for it.

Verify the fix with the layer that actually gates it: a formatter/axis fix needs the e2e/browser suite that renders it, not only the unit test — a vacuous unit assertion (right value, never rendered) is exactly the bug class you were sent to fix. For a hover-only element, the regression test MUST use the right component/fixture AND actually hover; asserting absence on a component or state where the element never appears passes trivially and guards nothing.

Post one PR-feed comment that separates "fixed in <sha>" (per-item, with the mechanism and the pinning test) from "needs your decision" (per-item, with the evidence and the specific question). Call out the single highest-risk unverifiable item (the cross-service contract) explicitly so the author cannot miss it.

Loading a pure-logic Python module to probe it WITHOUT the package's heavy import chain: importing `pkg.sub.module` runs `pkg/__init__.py`, which can pull in optional deps absent on the host (e.g. an agent framework) and `ModuleNotFoundError` before your test runs. Load the single file directly instead:
```python
import importlib.util
spec = importlib.util.spec_from_file_location("mod", "src/pkg/sub/module.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
```
This works when the target module itself only imports stdlib. For FAA specifically, commit/push/lint/build/full-test still belong in the devcontainer, but a stdlib-only pure-logic probe like this is host-safe (no git/LFS/network touched).

When a Jev engineering scorer (halluc_guard/pr_gate) returns `{"status":"jev_unavailable"}` (no `TYPESAFE_API_KEY` or no network), the skill's fail-open means you own the verdict: fall back to empirical source verification (run the reproduction, read the source). That fallback is the stronger evidence here anyway — do not report the Jev-unavailable as a blocker or a reason you could not verify.

### 5. Reviewing a PR on a host your gh is not authed to

When `gh auth status` shows a different host than the PR (e.g. gh bound to an enterprise host, PR on public github.com):
- Read-only works without auth on a public repo: fetch the branch over HTTPS (`git fetch origin pull/<N>/head`), and hit the public REST API unauthenticated for metadata (`curl -s https://api.github.com/repos/<owner>/<repo>/pulls/<N>`). Pipe curl to `python3 -c` to extract title/author/base/head SHA/body.
- Before concluding you cannot post, check whether `git` itself has a credential for the PR's host even though `gh` does not: `git`'s osxkeychain/credential helper often holds a github.com token independent of the enterprise-bound `gh`. If a plain `git push` to the PR's remote succeeds, that same token can post the review — retrieve it with `printf 'protocol=https\nhost=github.com\n\n' | git credential-osxkeychain get` (reads `password=<token>`) and POST to `/repos/<owner>/<repo>/pulls/<N>/reviews` with `Authorization: token <token>`. Never print the token.
- Only if NO such credential exists: present the full structured review in chat and offer to post it once the user supplies a `GITHUB_TOKEN` for the host or runs `gh auth login -h <host>`.
- `GH_HOST=github.com gh ...` retargets the host but still needs credentials for it; it will 401 without them.
- When fixes are pushed to the PR during the same review, post the review as a COMMENT event (not Request-Changes) and say the blockers are already fixed in commit `<sha>` — downgrade the posture once the blocking items are resolved.

### 6. Report: verdict, verified gates, then severity-ranked findings

Lead with the verdict (Approve / Request Changes / Comment) and a one-line reason. Then a "Verification results" block stating what you ran and what it returned (test counts, build result, the base-vs-head tsc diff outcome, the pre-existing-failure confirmation). Then findings ranked Critical / Warning / Suggestion, each citing `path:line`. End with Looks-Good so the author sees what not to touch. Request Changes for any introduced functional bug or type regression even when the build/tests are green, because the build may not gate on it.

## Pitfalls

- Clean up when done: `git checkout <original-branch> && git branch -D pr-<N>`. A force-delete of the PR branch needs the branch not currently checked out.
- Never trust `build` to be a type gate. Separate the type check; a green build with failing `tsc --noEmit` is a real finding when the author claimed type-safety.
- A "pre-existing failure" claim is unverified until the same test fails on the base branch AND the PR did not modify it. Both halves are required.
- Raw error counts are meaningless on a repo with a dirty base; always `comm -23` the sorted head output against the sorted base output to get the introduced set.
- Distinguish a type error that is runtime-safe-by-luck (missing field coerces to the right default) from one that changes behavior (e.g. a split/child record not inheriting a parent flag). Both are worth flagging but at different severity.
- Before reporting a suite failure, confirm it is deterministic: rerun the full suite and the one file in isolation. A transient crash that appears once in a full run but not on rerun or in isolation (e.g. a sql.js/WASM "out of memory" from a timer firing after the test completed, or any cross-test leak) is flakiness, not a blocker — note it as flaky, do not count it as a hard failure. Only a failure that reproduces every run is a finding.
- A "regression test" that RE-IMPLEMENTS the logic under test inline (a local `simulateHandleX` copy of the component's guard) instead of importing and calling the real function does not guard the real code path — a genuine regression in the component would leave the test green. Flag it as a Suggestion: the test asserts the shape the author believes is there, not what ships. Verify a claimed regression test actually imports the symbol it protects.
- When the author headlines on-device/behavioural smoke as "N/N PASS," open the evidence report (e.g. `report.json`) before repeating the number. Scenarios can be marked PASS while their semantic/ML confidence scores sit below the gating threshold (passing only because that signal is advisory, not gating), or while the driven action was a no-op (`changed:false`, before-ids == after-ids). Report the PASS with the caveat the evidence actually supports, not the headline count.
