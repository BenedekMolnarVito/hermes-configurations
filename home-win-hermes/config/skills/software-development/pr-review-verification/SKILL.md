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

Not a substitute for github-code-review (fetch/diff/post/approve mechanics) or change-integration-analysis (planned-vs-branch overlap, not quality).

Makes a PR review evidence-backed instead of description-trusting. The github-code-review skill covers the mechanics (fetch, diff, post inline comments, approve/request-changes); THIS skill covers the step most reviews skip: independently proving or disproving the PR's own claims ("this failure is pre-existing", "build is clean", "no regressions") and catching the bug classes a diff-read alone misses.

Standing rule for this user: do not restate the PR author's claims as findings. Every claim in the PR body ("the one failing test is a pre-existing bug on the base branch", "build is clean", "every FR has tests") is a hypothesis to confirm against the base branch, not a fact. Report what YOUR execution returned, and name any claim you could not verify.

## Procedure

### 1. Check out the PR and run the gates the author claims pass

1. Fetch and check out: `git fetch origin pull/<N>/head:pr-<N> && git checkout pr-<N>`. node_modules usually already present on a sibling branch of the same repo; only `npm ci` if the lockfile changed.
2. Run the suite and build the author says are green (e.g. `npm run test`, `npm run build`). Record exact pass/fail counts.
3. Know what the build actually gates. `build` = `vite build` (esbuild) does NOT type-check — a PR can build clean and still carry TypeScript errors. If the author claims type-safety, run `npx tsc --noEmit` separately (see step 3).

### 2. Confirm a "pre-existing failure" against the BASE branch before accepting it

When the author blames a failing test on a pre-existing base-branch bug:
1. Verify the failing test is UNCHANGED by the PR: `git diff <base>...pr-<N> -- <test file>` and confirm the assertion lines show as context (unchanged), not `+` additions. A failing test the PR itself added is a different problem.
2. Run that one test on the base branch: `git checkout <base> && npx vitest run <file> -t "<test name>"`. If it fails identically there, the claim holds. If it passes on base, the PR introduced the failure.
3. Stash/restore cleanly around branch switches: `git stash -u` before `git checkout`, `git stash pop` after returning. Leaving the worktree dirty makes the next `git checkout` fail or carry edits across branches.

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

Check whether a test would have caught the bug: read the fixture timestamps. A boundary bug slips through when fixtures use mid-period values (day 15) and never the edge (last day, today). Flag the missing boundary test alongside the bug.

### 4b. A test that fails only under YOUR timezone is a test bug, not a code bug

Before reporting a date/time test failure as a regression, decide whether the TEST is tz-fragile. A `datetime-local` input holds a wall-clock value with no timezone; the component typically stores UTC via `new Date(local).toISOString()`. A test that enters `"2024-06-20T08:45"` and asserts the stored string `.toContain("08:45")` only passes when the runner's TZ is UTC (CI) — it fails under a non-UTC local TZ (CEST stores `06:45Z`). This is the usual root of a "pre-existing failure" on a tz-offset machine.
- Confirm it is tz-dependent, not real: run the one test under both timezones. `TZ=UTC npx vitest run <file> -t "<name>"` passes, `TZ=Europe/Budapest ...` fails => the test, not the code, is wrong.
- Fix the test to be tz-independent: assert against the component's own conversion, not a hardcoded literal — `const expected = new Date("2024-06-20T08:45").toISOString(); expect(saved.receivedAt).toBe(expected)`. This tests the real round-trip contract in any timezone.
- This is a legitimate in-review fix: a tz-fragile test is noise that masks real failures. Fix+push it, verify green under both `TZ=UTC` and the local TZ, and note it in the review rather than rubber-stamping the author's "pre-existing" claim.

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
