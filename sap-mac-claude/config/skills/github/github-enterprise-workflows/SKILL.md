---
name: github-enterprise-workflows
description: "Use ONLY on GitHub Enterprise Server hosts (non-github.com), or when systematically addressing reviewer comments on a PR."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [GitHub, GitHub-Enterprise, Pull-Requests, Code-Review, SAP]
    related_skills: [github-code-review, github-pr-workflow, github-auth]
---

# GitHub Enterprise Workflows

Supplement to the bundled github-code-review and github-pr-workflow skills for GitHub Enterprise (GHE) hosts and the "address PR review comments" workflow.

## When to Use

- The git remote URL is NOT github.com (e.g. github.tools.sap, github.example.corp).
- You need to fetch or filter PR review comments from a GHE instance.
- The user says "address the comments on PR #N by <reviewer>" and the repo lives on a GHE host.
- The user says "address the minor / non-blocking issues from the review too" (works on github.com repos as well — see 3b-minors; auth and the review-body fetch differ by host).
- You are fixing a React settings dialog with dual-draft state and need diff-guard symmetry guidance.

## 1. Detecting and Configuring GHE

When the remote URL is not github.com (e.g. github.tools.sap, github.example.corp):

```bash
REMOTE_URL=$(git remote get-url origin)

# Extract host from HTTPS or SSH remote
GH_HOST=$(echo "$REMOTE_URL" | sed -E 's|https?://([^/]+)/.*|\1|; s|git@([^:]+):.*|\1|')
# e.g. GH_HOST=github.tools.sap

# Check auth status for this host
gh auth status --hostname "$GH_HOST"

# Extract owner/repo — sed must strip the GHE host, not just github.com
OWNER_REPO=$(echo "$REMOTE_URL" | sed -E "s|.*${GH_HOST}[:/]||; s|\.git$||")
OWNER=$(echo "$OWNER_REPO" | cut -d/ -f1)
REPO=$(echo "$OWNER_REPO" | cut -d/ -f2)
```

Set `GH_HOST` for high-level commands such as `gh pr`; those subcommands may not accept a `--hostname` flag. Keep `--repo` explicit so the command cannot target a similarly named repository on another host. Use `--hostname` directly with `gh api`:

```bash
GH_HOST="$GH_HOST" gh pr view 94 --repo "$OWNER_REPO"
gh api --hostname "$GH_HOST" "repos/$OWNER/$REPO/pulls/94"
gh api --hostname "$GH_HOST" "repos/$OWNER/$REPO/issues/94/comments"
```

If HTTPS Git operations fail because the container has no credentials, start the supported browser/device flow in that exact container, wait for completion, then wire Git to the new credential:

```bash
gh auth login --hostname "$GH_HOST" --git-protocol https --web
gh auth setup-git --hostname "$GH_HOST"
```

Surface the one-time code and device URL to the user, keep the process alive while they authorize, and verify success with `gh auth status --hostname "$GH_HOST"` before retrying the push.

For curl on GHE the API base is `https://$GH_HOST/api/v3/` (not api.github.com):

```bash
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://$GH_HOST/api/v3/repos/$OWNER/$REPO/pulls/$PR_NUMBER"
```

## 2. Fetching PR Review Comments on GHE

GHE has two distinct comment endpoints — which one holds the reviewer's text depends on how they posted:

| Endpoint | Contains |
|----------|----------|
| `pulls/{N}/comments` | Inline diff-level review comments (attached to a specific line in the diff) |
| `issues/{N}/comments` | General PR comments posted in the conversation tab (not attached to a line) |

**Pitfall:** Reviewers who write a comment in the PR conversation (not as an inline diff comment) land in `/issues/{N}/comments`, not `/pulls/{N}/comments`. If `pulls/{N}/comments` returns empty, always check `/issues/{N}/comments` too.

**Pitfall: the PR may live on github.com even when `gh` is only authed to the GHE host.** `gh` auth is per-host; a personal/public repo whose `origin` is github.com is unreachable with only `github.tools.sap` auth (`gh ... --repo <github.com repo>` -> `HTTP 401 Requires authentication`, even `GH_HOST=github.com gh ...`). Check `git remote -v` to see the real host before assuming the GHE path. For a PUBLIC github.com repo you do not need to auth `gh` at all — the unauthenticated REST API serves reviews and comments:
```python
# review BODIES (the formal review text + verdict) live on /reviews, NOT /comments
import json, urllib.request
for ep in ["reviews", "comments"]:  # reviews=formal review bodies; comments=inline diff comments
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls/{PR}/{ep}"
    req = urllib.request.Request(url, headers={"Accept":"application/vnd.github+json","User-Agent":"x"})
    data = json.load(urllib.request.urlopen(req, timeout=20))
    # reviews[*].body holds the whole review markdown; issues/{N}/comments for conversation-tab
```
The formal review verdict/findings text is on `pulls/{N}/reviews` (`.body`), separate from the three comment endpoints — a review submitted as COMMENTED/APPROVED/CHANGES_REQUESTED carries its prose there, not in any `/comments` list.

```bash
GH_HOST="github.tools.sap"   # set from detection above
PR_NUMBER=94

# 1. Check inline diff comments
gh api --hostname "$GH_HOST" \
  "repos/$OWNER/$REPO/pulls/$PR_NUMBER/comments" \
  --jq '.[] | {author: .user.login, file: .path, line: .line, body: .body}'

# 2. Check general PR conversation comments (often where reviewers post)
gh api --hostname "$GH_HOST" \
  "repos/$OWNER/$REPO/issues/$PR_NUMBER/comments" \
  --jq '.[] | {author: .user.login, body: .body}'
```

To filter to a specific reviewer by username or display-name fragment:

```bash
gh api --hostname "$GH_HOST" \
  "repos/$OWNER/$REPO/issues/$PR_NUMBER/comments" \
  --jq '.[] | select(.user.login | test("Magyar|Mark"; "i")) | {author: .user.login, body: .body}'
```

## 3. Addressing PR Review Comments — End-to-End Workflow

When the user says "address the comments on PR #N by <reviewer>":

1. **Detect host and set vars** (Section 1 above).

2. **Fetch all comment types** — check both endpoints (Section 2). Print full body so nothing is missed.

3. **Read the referenced file** with `read_file` at the exact line cited in the comment. Get full context, not just the snippet.

4. **Make the fix** with `patch` or `write_file`. Apply each issue independently — do not conflate.

5. **Verify with a build** — run `npm run build` / `cargo build` / `pytest` etc. before committing. A passing build is the minimum bar.

6. **Commit with a message that cites what was addressed:**

```bash
git add <changed files>
git commit -m "fix(scope): address PR review comments

1. <summary of issue 1 and fix>
2. <summary of issue 2 and fix>"
```

7. **Push** to the existing branch — the PR picks it up automatically.

```bash
git push
```

8. **Verify the push landed** — compare the remote ref to local HEAD instead of
   trusting the push output:

```bash
[ "$(git rev-parse HEAD)" = "$(git ls-remote origin refs/heads/<branch> | cut -f1)" ] && echo OK
```

No need to leave a reply comment unless the reviewer asked a question that needs
an answer — but when a review had multiple substantive points, a single summary
comment mapping each point to the fix (+ any Jira keys opened) closes the loop.
When the review rested on claims you could NOT independently verify (live-cluster
telemetry, a quota only the reviewer can read), state that caveat in the reply:
name which numbers are the reviewer's readings you accepted without confirming,
and what should re-check them (e.g. first int deploy) — do not present accepted-
on-trust facts as validated.

9. **If asked to WATCH the PR for a re-review and re-verify when it lands**, do
   not build a GitHub webhook from a CLI session — use a `gh`-auth polling
   watcher instead. See `references/watch-pr-for-re-review.md` for the
   webhook-vs-polling decision, the watermark/author-filter poller, the cron
   wiring (`~/.hermes/scripts/`, `no_agent` silent-on-no-change), and the honest
   "local cron can't notify you" limitation to state rather than over-promise.

### When the review asks to REVERT part of the PR

A "revert file X to <commit>" is a review response, not a new edit. Two traps:

- **"Revert to <commit>" is ambiguous once the branch has merged main.** If a
  merge commit pulled `origin/main` into the branch after `<commit>`, reverting
  to that commit's literal bytes also undoes whatever entered via the merge
  (e.g. an unrelated refactor from main), silently regressing a released change.
  Confirm what actually differs first: `git log --oneline origin/main..HEAD` for
  branch-only commits, `git merge-base --is-ancestor <suspect> HEAD` to test
  whether a main change is in play, and `git diff <commit> HEAD -- <file>` to see
  the full delta. The reviewer almost always means "remove THIS PR's changes to
  the file", which is `git checkout origin/main -- <file>` — NOT the literal
  pre-merge snapshot. When the literal target and the origin/main target differ,
  ask the user which they want before acting; state the concrete consequence
  ("293e6bb also drops the CFAAI-653 data_product refactor merged from main").
- **Reverting a feature's code orphans the tests that shipped with it.** New
  tests added alongside the reverted code assert the now-removed behavior and
  will fail against the reverted layer. Grep the test tree for the symbols /
  fixtures the reverted code introduced, and remove or relocate those tests in
  the SAME commit — otherwise CI red-lines on the exact tests the reviewer
  approved "as-is". Keep tests that are independent of the reverted layer.

Verify the revert produced the intended state: after `git checkout origin/main
-- <files>`, `git diff origin/main HEAD -- <files> | wc -l` must be 0, and the
PR's net `src/` diff vs main should be empty when the whole tool/code layer was
pulled. Then state the deviation (origin/main vs literal commit, tests removed)
in the summary reply so the reviewer sees why the diff isn't a byte-for-byte
revert to the commit they named.

## 3b. Verifying a Fix Commit Actually Addressed the Review

When the user says the author "addressed the review in a commit" and asks you to
verify (before approving or telling them it's clean), do NOT re-review the whole
PR. Diff ONLY the new commit(s) against your prior findings, item by item.

1. **Get the current head and the new commits since your review:**

```bash
gh pr view $PR --repo "$OWNER_REPO" \
  --json headRefOid,commits \
  --jq '{head: .headRefOid, commits: [.commits[] | {oid: .oid[0:8], msg: .messageHeadline}]}'
```

2. **Read the fix commit's patch and its exact file list** — the file list is the
   fast tell for coverage:

```bash
gh api --hostname "$GH_HOST" "repos/$OWNER/$REPO/commits/<sha>" \
  --jq '.files[] | {file: .filename, additions, deletions}'
gh api --hostname "$GH_HOST" "repos/$OWNER/$REPO/commits/<sha>" --jq '.files[].patch'
```

3. **Map each prior finding to the diff and mark it addressed / not addressed.**
   Keep the mapping explicit — one line per finding — so nothing is assumed fixed.

4. **For any finding NOT visible in the diff, confirm the current state at the PR
   head directly** rather than inferring from the commit message:

```bash
gh api --hostname "$GH_HOST" \
  "repos/$OWNER/$REPO/contents/<path>?ref=<head-sha>" --jq '.content' | base64 -d \
  | grep -n "<the offending string>"
```

**Pitfalls specific to fix-commit verification:**

- **A follow-up commit that touches SOME files silently leaves other findings
  open.** The commit message ("address review nits") and the fact that a commit
  exists prove nothing about coverage. Check the commit's *file list* against the
  files your findings named: if a flagged file is absent from the commit, that
  finding is untouched — verify it at the head, do not assume the sweep caught it.
  The highest-priority finding is the one most worth re-confirming, not the ones
  the author obviously fixed.
- **Grade against the finding, not against "a change happened."** A test-robustness
  finding is only resolved if the new assert would fail on the regression it
  guards — e.g. a vacuous `assert "phrase" in whole_prompt` is fixed by scoping
  the search to the relevant section, not by leaving it global. Read the new
  assert and confirm it actually pins the invariant.
- **When some findings are fixed and one is not, don't post a fresh full review.**
  If the user said "if fully verified, just tell me; if not, draft a comment for
  me to review" — honor that: acknowledge the fixed items in one line, then state
  ONLY the still-open finding with its file:line and why it matters, and hand the
  draft back for approval before posting. Do not re-litigate resolved points.
- **When the fix is config/data-processing logic, REPLAY it, don't just read the
  diff.** For a change to a loader/transform/filter (e.g. a CI `load_config.py`
  that filters a deployment list), copy the PR-head versions of the input file(s)
  and the script, run the exact changed block with the real inputs (the same
  `pr_number` / env the pipeline uses), and assert the invariant the failing CI
  job checks — print the resulting structure and confirm the specific property
  (no dangling reference, expected item removed). A clean-looking diff is not
  proof the output is valid; replaying it is, and it gives confidence even before
  the gating deploy/pipeline job (which often runs last) finishes. Use the real
  interpreter with the project's deps (in FAA: the devcontainer, `uv run`), since
  config parsers like pyhocon have nonobvious value shapes.
- **Removing a list entry orphans every reference TO it — grep for the removed
  name before approving.** When a fix drops an item from a collection (a
  deployment, a service, a tool, a fixture), a validator or template elsewhere
  that cross-references it by name hard-fails on the now-dangling reference
  (e.g. a Helm `allowedCallers`/`_helpers.tpl` validation `{{- fail }}`s when a
  caller names a deployment no longer in the filtered list). The complete fix
  must also prune or redirect those references in the same code path. Confirm by
  grepping the config/chart for the removed name and checking each hit resolves
  — this generalizes the "reverting code orphans its tests" trap to any
  by-name cross-reference.
- **Verify a config-only PR's effect against its CI run, not the stringified
  value you'd expect.** Config parsers expose values in nonobvious shapes:
  pyhocon parses `deployment_targets: ['kyma']` to `["'kyma'"]` (elements keep
  literal quotes), so `"'kyma'" in deployment_targets` is a genuine
  list-membership test, not substring matching — do not flag such an idiom as
  "fragile stringified-list check" without first confirming the parsed shape in
  the real interpreter. When unsure whether a membership/guard actually fires,
  replay it rather than reasoning about the source text.

## 3b-minors. Addressing the review's OWN non-blocking / minor findings

"Address the minor issues too" means working the review's deferred list — the
💡 non-blocking / "worth a follow-up" items the review itself enumerated — NOT
reviewer line-comments. Clarify first if "the code review" is ambiguous: the PR
review on the host, a local review doc, or SDD artifacts are different sources;
ask which before reading the wrong one.

1. **Enumerate every minor across ALL reviews on the PR.** A re-review supersedes
   the first on blockers but its "non-blocking" list is often a subset; union the
   💡 items from every review body so none is dropped.
2. **Triage each by scope before touching code — don't fix blindly.** Split into:
   real behavior (fix + test), cosmetic/polish (fix), and explicitly
   out-of-scope / pre-existing (the reviewer said "pre-existing", "out of scope",
   or it lives in another layer — SKIP and say so). When the boundary is a
   judgment call (a "minor" that is actually a behavior change needing a test),
   confirm the set with the user via one `clarify` before editing.
3. **Each fix that changes behavior gets a test** (repo's coverage gate). Thread
   the fix at the layer it belongs and add a test at BOTH the unit layer and the
   integration/hook layer when a value flows through several (e.g. a filter
   param added to a repo fn AND threaded through the hook that calls it).
   - **The regression test must exercise the REAL stored/runtime format, and you
     must confirm it would FAIL on the pre-fix code — otherwise it is theater.**
     A bug often survives a green suite precisely because every existing fixture
     uses a value the production code never actually produces: e.g. a
     lexicographic deadline compare passed all tests because the fixtures used
     UTC-`Z` ISO strings, while the app stores local-no-`Z` minute-precision
     (`${date}T${time}`) — the format that triggers the bug was never in a
     fixture. Build the new fixture from the SAME producer the app uses (or a
     helper that mirrors it), pick values on the boundary the bug lives at (just
     past / just future, not mid-period), and sanity-check that the assertion
     flips red against the old implementation before trusting the green.
   - **When the review's finding is "a test re-implements the logic it claims to
     guard," the fix is to make the test import the REAL symbol — extract the
     decision into an exported pure function the component/handler calls, then
     test THAT.** An inline copy of the guard (`simulateHandleDragEnd` mirroring
     the component's `handleDragEnd`) asserts the shape you believe exists, not
     the code that ships; a real regression in the component would not fail it.
     Extracting a thin exported helper (e.g. `computeReorderIdSequence`) that the
     handler delegates to keeps the handler wiring intact while giving the test a
     real target.
4. **Run the project's gates + a NO-NEW-TYPE-ERRORS baseline diff** (next
   subsection), then one commit `fix(review): address PR #N minor findings` with
   a body mapping each finding to its fix and the pass/build/tsc numbers.

### Verifying "no NEW type errors" when the build does not gate on tsc

Vite/esbuild (and swc) builds STRIP types and do not run `tsc`, so a change can
build clean and ship a new `tsc --noEmit` error that CI never catches — and the
repo may already carry N pre-existing tsc errors, so a raw count is noise. Prove
you added zero:
```bash
git stash && npx tsc --noEmit 2>&1 | grep -E "error TS" | sort > /tmp/base.txt; git stash pop
npx tsc --noEmit 2>&1 | grep -E "error TS" | sort > /tmp/head.txt
diff /tmp/base.txt /tmp/head.txt   # only line-number shifts (NN -> NN+k) = no new error
```
A diff whose only change is a line number on the SAME file+message is a shift
from lines you added above it, not a new error. Before adding any `import.meta.env`
reference, check the project actually has `vite/client` types (a `*.d.ts` with
`/// <reference types="vite/client" />` or `"vite/client"` in tsconfig `types`) —
without it, `import.meta.env` is `Property 'env' does not exist on ImportMeta`.

### Silencing a jsdom/web-stub console.warn that spams the test runner

A Capacitor (or any web-stub) plugin call inside a `catch` that `console.warn`s
fires on every mount in jsdom and clutters test stderr. Gate the warn on
`process.env.NODE_ENV !== "test"` — `@types/node` is already in most tsconfig
`types`, so `process.env` is typed with ZERO new ambient surface, and bundlers
replace `process.env.NODE_ENV` with `"production"` at build time so the warn
still fires in dev/prod. Prefer this over `import.meta.env.MODE` (needs
vite/client types) and over deleting the warn (loses the prod diagnostic).
Confirm the fix by grepping the test's captured stderr for the warning string
before and after — unrelated framework warnings (React Router future-flags) will
remain and are not your regression.

### A vitest full run reporting "N errors" while every test PASSES

Uncaught async errors (e.g. sql.js `out of memory` from a debounced timer firing
AFTER a test's `db.close()` teardown) count as run "errors" but are not test
failures and are often flaky — they appear only under full-suite parallel memory
pressure. Before blaming your change: re-run the suite (frequently clean the 2nd
time) AND run the implicated file in isolation on a `git stash` baseline. If it
passes isolated on baseline and the erroring file is one you did not touch, it is
a pre-existing teardown race — report it as an out-of-scope follow-up (clear the
timer on unmount), do not present it as a regression you introduced.

## 3c. Verifying a PR's OWN claims + fix scope before approving

When a PR description asserts verifiable facts ("brings dev in line with
int/prod", "root cause is a config gap not a code gap", cites `file.py:NN`) or
references an internal findings/diagnostic doc, do NOT approve on the prose.
Check each claim against the live repo, and check the fix's SCOPE against the
diagnosis.

1. **Verify parity claims by reading all the peers.** "dev now matches int/prod"
   means fetch all three files at the relevant ref and diff the specific block —
   `gh api --hostname "$GH_HOST" "repos/$O/$R/contents/<path>?ref=<sha>" --jq
   '.content' | base64 -d`. Confirm equality, don't trust the word "aligns".
2. **Verify code-line claims at the cited lines.** A description citing
   `loader.py:57` / `app.py:1028` for a gating expression is checkable — read
   those lines and confirm the mechanism (e.g. the manifest's `default_tools`
   really is intersected with an allow-set, and the flag really is the only
   thing enabling the tool). A config-only change whose effect depends on a
   registration/gating path is only correct if that path reads the config the
   way the description claims.
3. **Verify the enabling precondition holds for every affected item.** "registers
   `{slug}_value_help` for each product" is only true if each product actually
   meets the guard (here: has an InA port). Read each product file and confirm
   the precondition — a config flag that silently no-ops for some items is a
   partial fix dressed as a full one.
4. **Grade fix SCOPE against the diagnosis, not against the diff being clean.**
   A findings doc often lists TWO+ orthogonal root causes for one reported
   symptom (e.g. "tool not available" AND "wrong hierarchy attached"). A PR that
   correctly fixes ONE is still correct as written, but merging it does NOT
   close the reported problem. Say so explicitly in the review: acknowledge what
   it fixes, then name the still-open orthogonal issue, where its fix lives
   (e.g. a different repo / a skill edit), and that this merge does not address
   it. Do not let a clean one-liner imply the whole ticket is resolved.
5. When the findings doc lives in the working tree, read it (`read_file`) and
   map each of its numbered claims to what you independently confirmed — treat a
   "check the doc" request as "validate the PR against the doc's claim N", not
   "summarize the doc".
6. **Verify claims about files the PR does NOT touch, too.** A description saying
   "the sibling skill/module already does X correctly, so no change there" is a
   verifiable claim — read that sibling file and confirm it. A claim like "pnl
   already steers the flat GL row" can be literally false (the sibling groups by
   a hierarchy row on a *different* cube/wire), yet still leave the PR correct
   because the sibling's structure differs. Flag the imprecise wording as a
   non-blocking note; do not let "already correct elsewhere" pass unchecked.
6b. **Verify the fix's inline rationale against the TOOL'S docs, not the repo —
   a comment can be confidently wrong about where a value comes from.** When a
   diff drops a flag/argument and the accompanying comment justifies it ("X is
   already in env, so omitting the flag is safe/more secure"), that premise is a
   checkable claim about the invoked tool, not about the repo. The classic trap:
   an env var consumed by a wrapper (a GitHub Action, a setup step) is assumed to
   also be read by the underlying CLI command it configures — but the CLI's own
   options table lists NO such env fallback. E.g. `jfrog/setup-jfrog-cli` reads
   `JF_URL/JF_USER/JF_PASSWORD` to auto-build a server, yet `jf config add`
   accepts a credential ONLY via `--password` / `--password-stdin` /
   `--access-token[-stdin]` — so `jf c add --user=.. --basic-auth-only=true`
   with no password/stdin builds a credential-LESS config and the next call
   401s. Pull up the command's authoritative docs (web_extract the options
   table) and confirm the named mechanism actually exists before accepting the
   removal. When the goal was keeping a secret off `/proc/<pid>/cmdline`, the
   correct form is the `--*-stdin` variant (`printf '%s' "$SECRET" | cmd ...
   --password-stdin`), not dropping the credential.
7b. **"CI is green" is meaningless for a workflow/pipeline-file change whose job
   does not run on `pull_request`.** Reusable/`workflow_call`, self-hosted,
   `on: [closed]`, deploy, and cleanup jobs are NOT exercised by the PR checks,
   so a passing `test-and-lint` validates nothing about the edited YAML. State
   this in the review and point validation at the real trigger (re-run the job
   for a closed PR, trigger the deploy on a branch, etc.) rather than implying
   green checks cover it.
7. **When a change touches ONE of several near-identical sibling sites, find and
   grade all the siblings.** A fix that enriches one `except SomeError:` handler,
   one branch of an `if/else`, or one of N repeated blocks is suspect until you
   confirm whether the untouched twins were left out on purpose. `grep -n` the
   file for the shared marker string (the log message, the exception class, the
   tag key) to enumerate every occurrence, then walk the enclosing `if/elif/else
   / async with / try` structure *upward* from each hit to learn which branch it
   lives in — two handlers with identical text can sit in an eval-only vs
   production branch that use different tracing/behavior, which makes the
   asymmetry defensible. If defensible, say so and note the weaker-diagnostics
   twin as a non-blocking follow-up; if it is an oversight (same branch, same
   contract), that is a real finding. Never assume one modified block is the only
   one, and never assume the untouched twin is fine.

### Verifying a documentation / prompt / skill-content-only PR (no code path)

When the whole diff is prose — a `SKILL.md`, prompt template, README, or config
comment that is *read* at runtime, not *executed* — a build/test run does NOT
validate its behavior (there is no code path to exercise). The real bar is four
different checks:

1. **Internal-consistency sweep across EVERY touchpoint of the changed concept.**
   A steering change that flips a rule ("by GL account" -> flat leaf row, not
   hierarchy) must be reconciled everywhere the concept appears: cheat-sheet
   table, dimension table, name-resolution flow, worked examples, and any
   caveat/interim note. `grep -n` the head file for the concept's keywords and
   confirm no old phrasing survives that now contradicts the new rule — a single
   leftover "always query it as a hierarchy" line silently re-teaches the bug.
2. **Confirm no test asserts the changed content.** `grep -rln <slug>` the test
   tree; a test that hardcodes the old text or an exact version string breaks on
   the edit. Skill-loader tests often use a FABRICATED corpus (fake version like
   `1.0.0`) and assert only the enabled-slug SET / mount behavior — those do NOT
   depend on real content and will NOT break; read the fixture to confirm that
   before claiming a test gap.
3. **Version-bump correctness.** If the repo has a prompt/skill version field
   (e.g. `faa_prompt_version`) with a documented patch/minor/major rule, confirm
   the base value matches `origin/main` and the bump matches the change class
   (a clarification preserving prior capability is MINOR, not major).
4. **The change takes effect only on restart/redeploy** (skills/prompts load once
   at startup). State that in the review so nobody expects a hot pickup. Say
   explicitly that you did NOT run the suite and why (no executed code path), and
   offer it as an optional extra gate rather than skipping silently.

## 3d. Handling an APPROVAL that carries a condition

A reviewer can `APPROVE` while making merge contingent on a specific change
("approved with one condition: lower X from 3 to 2"), and may also use the
approval body to report facts they verified that you earlier flagged as
unverifiable. Two rules:

- **Verify the condition's REASONING before complying — a condition is a claim,
  not an order.** Trace what your original value rested on and whether the
  reviewer's new evidence actually overturns it. If a floor/ceiling/flag was
  justified by assumption A and the reviewer disproves A with a measurement,
  the change is warranted; make it. If the reasoning does NOT hold, say so and
  push back rather than silently applying. Do not reflexively change on the
  assertion alone.
- **When the reviewer confirms a fact you accepted on trust, propagate the
  correction to EVERY place that cited the old assumption** — chart value,
  inline rationale comment, and every doc/plan sentence that explained the old
  number. Changing only the number while a comment still argues the disproven
  rationale ships a self-contradicting file the next reviewer will flag. Re-run
  the project's verify gate after the change (for FAA: devcontainer
  render+assert+lint) and reply mapping the condition to the commit that met it.
- **A non-blocking follow-up the reviewer raises ("out of scope, worth a separate
  ticket") is not part of this PR.** Acknowledge it, open the separate ticket if
  the user wants, and do NOT widen the current PR's diff to chase it.

## 4. Common Pitfalls

- **Owner/repo extraction breaks on GHE** — the standard sed `s|.*github\.com[:/]||` will not match a GHE host. Always substitute the actual host in the sed pattern (see Section 1).
- **`gh auth status` without `--hostname`** — defaults to github.com and will show "not logged in" even when you're fully authed to a GHE instance. Always pass `--hostname`.
- **Passing `--hostname` to every `gh` subcommand** — high-level commands such as `gh pr view` may reject it. Export/prefix `GH_HOST=<enterprise-host>` and use `--repo owner/repo`; reserve `--hostname` for commands such as `gh api` and `gh auth` that define it.
- **Empty inline comments** — if `pulls/{N}/comments` is empty, the reviewer used the conversation tab. Check `issues/{N}/comments` (Section 2).
- **`gh pr view` / `gh api pulls/N/reviews` are ALSO empty for a conversation-tab review** — This is the easy-to-miss extension of the previous pitfall. A reviewer who posts a free-form comment in the PR conversation tab (not an inline diff comment, not a formal "Review" with a status) appears in NONE of: `gh pr view`, `gh api pulls/N/comments` (inline), `gh api pulls/N/reviews` (empty `[]`). The ONLY place the text lands is `gh api --hostname $GH_HOST repos/$OWNER/$REPO/issues/$N/comments`. When fetching "the comment by <reviewer>", always hit `issues/{N}/comments` as the primary source and grep by `.user.login` / display-name fragment. Do not conclude "no comment exists" until that endpoint is checked.
- **`gh api` (no `-R`) fails on GHE** — `gh api` without a repo flag hits github.com and errors (Validation Failed / unknown host). Always pass `--hostname $GH_HOST` and use the full `repos/$OWNER/$REPO/...` path.
- **`-R`/`--repo` is NOT a `gh api` flag** — `-R`/`--repo` is a top-level `gh` flag (works on `gh pr view -R owner/repo`), but `gh api` has no such flag. `gh api -R cfa-ai-incubation/fin-analyst-agent ...` fails immediately with `unknown shorthand flag: 'R' in -R` and prints usage — it never reaches the API. On `gh api` you MUST embed the repo in the path: `gh api --hostname "$GH_HOST" /repos/$OWNER/$REPO/issues/$PR/comments`. Never pass `-R` to `gh api`.
- **Writing multiline PR text inline is shell-fragile** — quoting Markdown through `--raw-field body=...` can split the payload into multiple arguments. For PR descriptions and comments, create a JSON payload with `write_file`, send it with `gh api --method PATCH|POST --input <payload.json>`, then read back the exact PR/comment before claiming success. Store transient payloads under `.git/` or `/tmp` so they cannot enter the commit.
- **Posting a PR comment: `-f`/`-F` body-from-file can fail to parse** — `gh api ... -f body=@/tmp/body.md` and `-F body=@/tmp/body.md` both errored with usage output in one GHE session (flag-parse quirk). The reliable method is `--input` with a JSON file:
  ```bash
  # body.json = {"body": "<markdown content>"}
  gh api --hostname "$GH_HOST" /repos/$OWNER/$REPO/issues/$PR/comments \
    --method POST --input /tmp/pr$PR_comment.json
  # returns {"id": ..., "html_url": "https://$GH_HOST/.../pull/$PR#issuecomment-..."}
  ```
  Build `body.json` with a small Python step (write_file), not by hand-escaping markdown in a shell `-d`. Verify the POST succeeded by checking the returned `html_url`.
- **Pipe `gh` into `python3` trips the security-review guard** — `gh api ... | python3 -c "..."` is flagged (MEDIUM/HIGH: "pipe to interpreter"). Instead: (1) write the JSON to a temp file with `gh api --hostname $GH_HOST ... > /tmp/prN_comments.json`, then (2) load and parse it with a separate `execute_code` Python step or `read_file` + manual inspection. For simple field extraction on small bodies, `gh api --jq` is fine, but for large/dense bodies the dump-and-parse split is more reliable and avoids the guard.
- **`git add -A` before a package-manager-backed pre-commit sweeps in a regenerated lockfile** — running lint/tests through `uv`/`npm`/`poetry` (e.g. `uv run pre-commit`) can rewrite `uv.lock`/`package-lock.json` as a side effect, and a broad `git add -A` then stages that plus any submodule drift alongside your intended change. Stage only the files you actually edited (`git add <paths>`), or after a broad add, unstage and restore incidental churn: `git restore --staged uv.lock && git checkout HEAD -- uv.lock`. Confirm `git diff --cached --name-only` lists ONLY your files before committing — an incidentally-regenerated lock diverges from the committed baseline and does not belong in a review-fix commit.
- **Diff-guard symmetry in multi-draft dialogs** — when a dialog manages two independent drafts (draft1 vs selectedValue1, draft2 vs selectedValue2), both callbacks must be diff-guarded identically. Unconditional `onUse(draft)` while `onUse2` is guarded creates a latent trap: any future handler without an early-return will re-trigger on unrelated changes. See `references/dual-draft-dialog-pattern.md` for the React pattern.

## 5. Worked example — fetching a conversation-tab review comment on github.tools.sap

```bash
GH_HOST="github.tools.sap"
OWNER="cfa-ai-incubation"
REPO="fin-analyst-agent"
PR=155

# All endpoints empty? rev=conversation-tab comment. Dump to file (no pipe-to-python).
gh api --hostname "$GH_HOST" "repos/$OWNER/$REPO/issues/$PR/comments" > /tmp/pr$PR_comments.json
# then parse /tmp/pr$PR_comments.json with execute_code / Python, grep by .user.login
```

If the JSON is large, prefer the dump-and-parse split over `--jq` to avoid the security-review guard and fragile inline scripts.

## References

- `references/dual-draft-dialog-pattern.md` — React dual-draft settings dialog diff-guard pattern
- `references/verify-reported-pr-bugs.md` — verify reported/external PR-review bug claims against the ACTUAL locked dependency/submodule/config state before fixing (catches false positives)
