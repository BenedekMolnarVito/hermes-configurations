---
name: verify-pr
description: "Use to address a PR's latest review end-to-end."
version: 2.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [pr, review, github, verify, fix, commit, summary, gh-cli, multi-agent]
    related_skills: [jev-engineering, synthesis-agent, github-code-review, github-pr-workflow]
---

# verify-pr

End-to-end loop for addressing a PR's latest review. Pulls every review issue,
fans out cheap parallel subagents to confirm each against real source, synthesizes
findings into a compact handoff packet, then — from that distilled packet — asks
any product calls, applies fixes, verifies, commits, pushes, and posts ONE
structured summary comment. Recurring task — run it the same way every time.

## When to Use

Use when the user asks to work a PR's latest review end-to-end: verify /
confirm the review issues, debug-fix them, commit + push, and post a structured
summary of what was addressed. Trigger phrases: "verify-pr", "verify the PR
review", "address the review (comments/issues) and push", "debug-fix the review
and summarize".

Don't use for: authoring a brand-new PR (github-pr-workflow), reviewing
someone else's PR you did not author (github-code-review), or issue→PR
implementation (github-issue-to-pr).

## Preconditions

- `gh` CLI authed for the repo's host (may be GitHub Enterprise, not github.com).
  Derive `OWNER/REPO` from `git remote get-url origin`. Confirm with `gh auth status`.
- You're on the PR's branch, or know the PR number. `gh pr status` shows the
  current-branch PR.

---

## Phase 1 — Gather ALL review issues (do this inline, before spawning spokes)

`gh pr view N --comments` hides inline review threads. Pull all three sources
and use timestamps to identify the LATEST review:

```bash
OWNER_REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
# Review summaries (state: APPROVED/CHANGES_REQUESTED/COMMENTED)
gh api repos/$OWNER_REPO/pulls/N/reviews \
  -q '.[] | "[\(.submitted_at)] \(.user.login) state=\(.state)\n\(.body)\n---"'
# Inline review comments (anchored to path:line) — the ones --comments hides
gh api repos/$OWNER_REPO/pulls/N/comments \
  -q '.[] | "[\(.created_at)] \(.user.login) \(.path):\(.line // .original_line)\n\(.body)\n---"'
# Issue-level (top-level) comments
gh api repos/$OWNER_REPO/issues/N/comments \
  -q '.[] | "[\(.created_at)] \(.user.login)\n\(.body)\n---"'
```

Produce a numbered list of every distinct issue: severity tag ([major]/[minor]/nit),
location (`path:line`), and the reviewer's exact claim. This list becomes the
input to Phase 2.

---

## Phase 2 — Fan out one cheap spoke per issue (parallel, Haiku tier)

For each issue in the list, spawn a subagent with this focused brief. All spokes
launch in a single batch — do NOT spawn sequentially and wait.

### Spoke brief template

```
You are a code-confirmation subagent. Your ONLY job is to confirm or reject
one reviewer claim against the actual source code. Do NOT fix anything.

CLAIM: {{reviewer_claim}} ({{path}}:{{line}})

TASK:
1. Read {{path}} (and any files the claim references).
2. Confirm whether the claim is true in the CURRENT code on this branch.
3. Return a terse verdict packet — nothing else.

VERDICT PACKET format (return exactly this, no prose):
VERDICT: CONFIRMED | REJECTED | PARTIALLY
EVIDENCE: <path:line — the exact lines that support or refute the claim>
FIX_DIRECTION: <one sentence — what a fix would do, or "N/A" if REJECTED>
NOTES: <anything the orchestrator must know — ambiguity, trade-off, product call needed>
```

Model/tier: `claude-haiku-4-5-20251001` (cheap, fast, bounded task — no reasoning needed).

### Why parallel Haiku spokes cut costs

Each spoke gets only the issue + the relevant file(s) — not the full PR diff, not
the conversation history, not every other issue. They run concurrently so the
wall-clock cost is the slowest single spoke, not the sum. The synthesis step then
distils ALL findings into one compact packet before anything enters the main session's
reasoning. Main context stays lean; expensive Sonnet/Opus thinking happens only
where it matters.

---

## Phase 3 — Synthesize spoke results (one cheap Haiku synthesis agent)

Once ALL spokes complete, dispatch ONE synthesis agent at the Haiku tier:

**Goal:** `Condense the raw spoke verdict packets into a structured handoff packet for the orchestrator.`

**Context to pass (verbatim — do not re-summarize):**
```
ORIGINAL GOAL: Address every confirmed issue from the latest review on PR #N.

SPOKE RESULTS:
Issue 1: <verbatim verdict packet from spoke 1>
Issue 2: <verbatim verdict packet from spoke 2>
...

CONSTRAINTS:
- Only fix CONFIRMED or PARTIALLY issues.
- REJECTED issues must be documented (not fixed) in the final PR comment.
- Flag any product calls (multiple valid remediations with user-facing trade-offs).
- Preserve exact path:line citations.
```

The synthesis agent returns one compact handoff packet (see synthesis-agent skill
for the exact packet format). After receiving it, discard all raw spoke outputs —
reason only from the packet for the rest of this workflow.

---

## Phase 4 — Product calls → ASK, don't guess

From the handoff packet's "Decisions Required" section: for any fix with more than
one reasonable remediation and a user-facing trade-off, surface it to the user
before touching code. Put the safest/recommended option first. Examples: storage-key
version bump vs. selective migration, behaviour-changing format vs. annotation-only fix.

---

## Phase 5 — Debug-fix (orchestrator applies fixes)

Work from the handoff packet's "Next-Action Plan". Fix root causes, not symptoms.
Match project style. Keep comments that reference changed behaviour accurate across
all touched files, not just the flagged line. Where the packet says FIX_DIRECTION,
follow it — don't invent a different approach.

---

## Phase 6 — Verify with the PROJECT's gate

Run the repo's documented verify commands (check `package.json` scripts / README /
AGENTS.md). Typical: `npx tsc -b`, `npx vitest run`, `npm run build` (NOT
`npx vite build` directly — the long-lived-server guard may block; the `build` npm
script is one-shot). For Python: `pytest tests`, `pre-commit run --all-files`.

If a test fails, determine whether it's YOURS or PRE-EXISTING:
`git stash`, re-run just that test, confirm it fails identically without your
edits, then `git stash pop`. Report pre-existing failures with that evidence —
don't absorb them into "my fix", and don't let them block the push.

NEVER fabricate test/build output. If the gate can't run, say so.

---

## Phase 7 — Commit + push

Stage ONLY the files you changed (not `git add -A`). Write a commit message that
names the PR, the severity, and what each fix addresses. Then `git push`. Never
`--no-verify`, never force-push a shared branch, never commit secrets.

---

## Phase 8 — Post ONE structured summary comment

`gh pr comment N -F -` with a heredoc. Build this from the HANDOFF PACKET, not
from re-reading the raw subagent outputs.

Structure:
- **Header:** commit SHA that was pushed (from `git rev-parse --short HEAD`).
- **Per confirmed issue:** severity tag + title → CONFIRMED/REJECTED verdict with
  evidence (path:line) → fix applied (what + why, incl. any product-call choice).
- **Per rejected issue:** why it was rejected (verbatim evidence).
- **`### Verification` block:** each gate command and its result; call out any
  pre-existing failure with the stash evidence.
- **Files changed** with +/- line counts.

Verify the comment URL returned by `gh`.

---

## Pitfalls

- `gh pr view --comments` hides inline review threads — always hit `/pulls/N/comments`
  (Phase 1).
- Spoke briefs must name exact files — generic "look at the codebase" briefs cause
  wandering and defeat the cost savings. If you can't name the file from the issue,
  read it yourself before spawning the spoke (THINK at hub, EXECUTE at spoke).
- Enterprise host: don't hardcode github.com. Let `gh` resolve the repo host.
- Confirm before fixing — a wrong reviewer claim fixed blindly adds a bug.
- A one-time localStorage/storage-key reset silently drops OTHER opt-ins; call that
  trade-off out and get sign-off (Phase 4) before choosing it.
- Pre-existing failures: prove with stash, report, don't absorb into "my fix."
- User upfront context ("already done", "do X instead of Y") covers SOME comments
  but not all. Always gather ALL reviewer issues via Phase 1 first — then map the
  user's instructions against that full list. Comments the user didn't mention still
  exist and must be fixed or explicitly skipped with a reason.
- "Already deleted by me" (and similar claims) must be verified with `git status`
  before accepting. Check `git diff --name-only origin/main...HEAD` to see everything
  still in the PR.
- If spokes are rate-limited (429), backoff 10s and re-dispatch only the affected
  ones. Never absorb a rate-limited spoke's work inline — a fresh subagent is cheaper
  than main-session sprawl.
- After synthesis, do NOT go back to raw spoke outputs. If you need more detail on a
  specific finding, dispatch a targeted follow-up spoke — don't re-read the whole batch.
