---
name: verify-pr
description: "Use to address a PR's latest review end-to-end."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [pr, review, github, verify, fix, commit, summary, gh-cli]
    related_skills: [jev-engineering, github-code-review, github-pr-workflow]
---

# verify-pr

End-to-end loop for addressing a PR's latest review: pull every review issue,
confirm each against the real source (don't trust the comment's framing),
debug-fix, run the project's verify gate, commit + push, then post ONE
structured summary comment that maps each addressed issue to its fix and the
verification evidence. Recurring task — run it the same way every time.

## When to Use

Use when the user asks you to work a PR's latest review end-to-end: verify /
confirm the review issues, debug-fix them, commit + push, and post a
structured summary of what was addressed. Trigger phrases: "verify-pr",
"verify the PR review", "address the review (comments/issues) and push",
"debug-fix the review and summarize".

Don't use for: authoring a brand-new PR (github-pr-workflow), reviewing
someone else's PR you did not author (github-code-review), or issue->PR
implementation (github-issue-to-pr).

## Preconditions

- `gh` CLI authed for the repo's host. The host may be GitHub Enterprise
  (e.g. `github.tools.sap`), NOT github.com. Derive `OWNER/REPO` from
  `git remote get-url origin` and let `gh` use the repo's configured host
  automatically (run `gh` commands from inside the repo). Confirm with
  `gh auth status`.
- You're on the PR's branch, or know the PR number. `gh pr status` from the
  branch shows the current-branch PR.
- Load `jev-engineering` for the PR-gate step (it fails open if no
  `TYPESAFE_API_KEY`).

## Step 1 - Gather EVERY review issue (three sources, not one)

`gh pr view N --comments` only shows ISSUE-level comments and misses inline
review threads. Pull all three sources via the API so nothing is missed, and
use timestamps to identify the LATEST review when there are several:

```bash
OWNER_REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
# Review summaries (state: APPROVED/CHANGES_REQUESTED/COMMENTED)
gh api repos/$OWNER_REPO/pulls/N/reviews \
  -q '.[] | "[\(.submitted_at)] \(.user.login) state=\(.state)\n\(.body)\n---"'
# Inline review comments (anchored to path:line) - the ones --comments hides
gh api repos/$OWNER_REPO/pulls/N/comments \
  -q '.[] | "[\(.created_at)] \(.user.login) \(.path):\(.line // .original_line)\n\(.body)\n---"'
# Issue-level (top-level) comments
gh api repos/$OWNER_REPO/issues/N/comments \
  -q '.[] | "[\(.created_at)] \(.user.login)\n\(.body)\n---"'
```

List every distinct issue with its severity tag ([major]/[minor]/nit) and
location. "Latest" = the most recent review submission and any comments at or
after its timestamp.

## Step 2 - CONFIRM each issue against real source (never trust framing)

For each issue: open the cited file at the cited line with `read_file` and
`search_files`. Verify the claim is actually true in the current code before
fixing. Reviewers (and review bots) can be wrong, cite stale lines, or
misread control flow. State for each: confirmed / partially / rejected, with
the evidence (`path:line`). Only fix confirmed issues.

Optional risk gate (jev-engineering): build a `pr_gate` job and run
`python3 ~/.hermes/skills/jev-engineering/scripts/pr_gate.py --input job.json`.
It fails open (`{"status":"jev_unavailable"}`) with no key - then rely on your
own confirmation above.

## Step 3 - Product calls -> ASK, don't guess

If a fix has more than one reasonable remediation with a user-facing
trade-off (the reviewer often lists options or says "product call"), use the
`clarify` tool to let the user pick. Put the recommended/safest option first.
Examples: storage-key version bump vs. selective migration vs. UI change.

## Step 4 - Debug-fix

Fix root causes, not symptoms. Match project style. Use `patch` for edits.
When fixing a stale comment/doc, prefer referencing a constant over
enumerating values so it won't rot again (if the reviewer suggested it, do
it). Keep comments that reference changed behavior accurate across all touched
files, not just the flagged line.

## Step 5 - Verify with the PROJECT's gate (and separate pre-existing failures)

Run the repo's documented verify commands (check `package.json` scripts /
README / AGENTS.md). Typical web/TS: `npx tsc -b`, `npx vitest run`,
`npm run build` (NOT `npx vite build` directly - the long-lived-server guard
may block it; the `build` npm script is one-shot).

If a test fails, determine whether it's YOURS or PRE-EXISTING: `git stash`,
re-run just that test, confirm it fails identically without your edits, then
`git stash pop`. Report pre-existing failures as such with that evidence -
don't let them block the push, and don't claim you fixed them.

NEVER fabricate test/build output. If the gate can't run, say so.

## Step 6 - Commit + push

Stage ONLY the files you changed (not `git add -A`). Write a commit message
that names the PR, the severity, and what each fix addresses. Then `git push`.
Never `--no-verify`, never force-push a shared branch, never commit secrets.
(For the FAA repo specifically: run git/test/build INSIDE the devcontainer -
see the faa-devcontainer-execution skill.)

## Step 7 - Post ONE structured summary comment

`gh pr comment N -F -` with a heredoc. Structure:

- Header line naming the commit SHA that was pushed.
- One section per addressed issue: the severity tag + title, a
  CONFIRMED/REJECTED verdict with evidence, and the fix (what + why, incl. any
  product-call trade-off the user chose).
- A `### Verification` block: each gate command and its result; call out any
  pre-existing failure explicitly with the stash evidence.
- Files changed with +/- line counts.

Use the SHA from `git rev-parse --short HEAD` / the push output - don't invent
it. Verify the comment URL returned by `gh`.

## Pitfalls

- `gh pr view --comments` hides inline review threads. Always hit the
  `/pulls/N/comments` API too (Step 1).
- Enterprise host: don't hardcode github.com. Let gh resolve the repo host.
- Confirm before fixing - a wrong reviewer claim fixed blindly adds a bug.
- A one-time localStorage/storage-key reset silently drops OTHER opt-ins; call
  that trade-off out and get the user's sign-off (Step 3) before choosing it.
- Pre-existing failures: prove with stash, report, don't absorb into "my fix."
- User upfront context ("already done", "do X instead of Y") covers SOME comments
  but not all. Always gather ALL reviewer issues via Step 1 first, then map the
  user's instructions against that full list — comments the user didn't mention
  still exist and must be fixed (or explicitly skipped with a reason). Do NOT
  treat the user's instructions as an exhaustive list of what needs doing.
- "Already deleted by me" (and similar claims) must be verified with `git status`
  before accepting — a partial deletion (one of two files removed) looks complete
  in conversation but leaves the other file in the PR diff. Check `git diff
  --name-only origin/main...HEAD` to see everything still in the PR.
