---
name: parallel-review-subagents
description: "Use in Claude Code (Agent tool) or Hermes to fan out N independent Agent subagents that each review one artifact (PR, file, test suite, config) in parallel, then synthesize their verdicts. Trigger when the user asks to review multiple files/PRs/artifacts at once, when running a multi-dimensional code review, or any time 'review N things in parallel' is the intent."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [subagents, delegation, code-review, parallel, orchestration]
    related_skills: [change-integration-analysis]
---

# Parallel Review Subagents

Orchestrate `delegate_task` fan-out for reviewing or analyzing several
independent artifacts at once — multiple PRs, multiple files, multiple docs.
Each child works in isolation and returns a distilled structured result, so the
heavy diff/file context never floods the main thread and reviews run
concurrently. This skill is the ORCHESTRATION layer; the domain skill (e.g.
`github-code-review` for PRs) supplies the review checklist and the posting
mechanics.

## When to Use

- "Review these N PRs independently / in parallel."
- Any fan-out where each child does a bounded read-heavy analysis and returns
  findings, and the children do not depend on each other's output.

## Procedure

### 1. Verify independence and reconcile the premise BEFORE spawning

Do not trust the word "parallel" in the request — confirm the artifacts are
actually independent and that the requested work exists:

- Check each target's real state first. For PRs: `gh pr view N --json state,url`.
  A request silently breaks if a target is already MERGED, or if two "PRs" live
  in *different repos* (a backend PR and its paired UI PR under one ticket).
- Different repos ⇒ zero file/merge overlap by construction; the only coupling is
  behavioral (both must state the same policy/contract). Same repo ⇒ compare
  changed-file lists for textual overlap first (see `change-integration-analysis`).
- Reviewing is READ-ONLY, so N PRs are ALWAYS parallel-reviewable even when they
  cannot all merge together. Do not treat file/merge overlap as a gate on whether
  to fan out — fan out regardless and turn the coupling into a first-class
  FINDING each child (and your summary) surfaces: which PRs collide, on which
  files, and what the safe merge order is. "Independent for review" and
  "independent for merge" are different questions; only the first gates the fan-out.
- Changed-file overlap UNDERSTATES coupling — also read each PR's COMMIT GRAPH
  with `git log --oneline origin/main..pr-N`. Two tells that a same-repo set will
  fight: (a) the same change appears as DUPLICATE cherry-picked commits across
  PRs (identical content, different SHA) — those files are guaranteed conflicts,
  the shared change belongs in exactly one PR; (b) a PR's real commits ship MORE
  than its title/body admits (a "raise the timeout" PR that also carries a
  schema/response-contract change), so approving the stated scope silently ships
  the rest. Flag both as warnings. For a version-stamped artifact (a
  `faa_prompt_version`-style semver in a skill/prompt file), confirm each PR's
  BASE value against `origin/main` — a PR based on a now-stale base
  (base 3.0.0 when main is 3.1.0) is already CONFLICTING and needs a rebase
  before it can merge; `gh pr view N --json mergeable` and
  `git merge-tree $(git merge-base origin/main pr-N) origin/main pr-N` confirm it.
- If the premise doesn't match reality — targets already implemented so it's
  review-only not "parallel work", or one is merged — make ONE clarify call
  ('what should the subagents actually DO?') before creating worktrees for work
  that doesn't exist.
- For paired artifacts under one ticket, actively look for cross-artifact
  consistency issues: the same user-facing string / contract / policy stated two
  ways is a real finding worth flagging on the offending side.

### 2. Isolate each child in its own worktree at the exact head SHA

Never let children mutate the user's working checkout, and never let two children
share a tree:

```bash
git fetch origin pull/$N/head            # for a PR; else fetch the target ref
git worktree add -f /path/to/scratch/wt-$N <HEAD_SHA>
```

Dump the diff/artifact to a scratch file and pass BOTH the diff path and the
worktree path to the child — the diff shows what changed, the worktree gives
full-file context and a place to run the build/tests.

### 3. Dispatch with a strict schema and review-only guardrails

- Tier by task weight: a scoped review with clear acceptance criteria is
  `standard`. Give each child an `output_schema` (verdict + findings[severity,
  location, note] + test/build result + head SHA).
- Instruct children **review-only: do NOT edit, commit, push, or post anywhere.**
  You post the results yourself so the final wording stays under your control and
  no child half-posts.
- Require the test/build result reported **honestly** as pass / fail /
  `blocked: <reason>`, and forbid fabricating a pass. A detached worktree often
  cannot run the suite (a devcontainer bound to the main checkout; uninitialised
  submodules). "Blocked — CI is the authoritative gate" is the correct answer,
  not an invented green; verify the honest status yourself before reporting it up.

### 4. A child can FINISH its analysis yet hang emitting the final output

A child that did all real work (files read, build run, findings compiled in its
transcript) can still sit at `status: running` indefinitely, looping on
"reconstruct the final JSON" — the analysis is done but the structured emit never
lands. Recover instead of waiting it out:

1. `delegate_task(action='list')` — a child no longer listed has already
   finished; one stuck at `running` for many minutes past its siblings is the
   suspect.
2. `read_file` its `live_transcript` (jump near the end with a large `offset`) —
   if the last lines are minutes-stale and the final assistant/think lines
   already show compiled findings, it's stuck, not working.
3. `delegate_task(action='stop', subagent_id=...)` — its partial result still
   returns, and the full findings are recoverable from the transcript (grep it
   for `severity` / `Warning` / `Suggestion` / `Looks-Good`). Reconstruct from
   the transcript rather than re-running the child.

The live transcript is the source of truth for a child's real progress — read it
to answer "how is subagent N doing?" rather than trusting the status field alone.

### 5. Consolidate, act, and clean up

- For the approve/request-changes/comment VERDICT, prefer a typed classifier over
  a free-text judgment when a TypeSafe/JEV key is available (`TYPESAFE_API_KEY`).
  `POST https://api.typesafe.ai/v1/systemone`, Bearer auth, one `choice` question
  per PR: state = the consolidated findings list, criteria = {approve,
  request_changes, comment} with a rubric each; the answer carries a calibrated
  `confidence` you can gate on (e.g. require high confidence + zero
  critical/warning findings to auto-approve, else request_changes). This keeps
  the merge gate deterministic and auditable rather than a per-run vibe. See the
  `typesafe-ai` skill for the request/response shape.
- Assemble the final reviews yourself from the returned schemas (and any salvaged
  transcript findings), then post via the domain skill's mechanism. On GitHub
  Enterprise hosts the reliable posting method is `gh api --hostname $GH_HOST
  .../issues/$N/comments --method POST --input body.json` — see
  `github-enterprise-workflows`.
- Remove every worktree: `git worktree remove --force <path> && git worktree prune`.
- Verify no checkout was left on a detached HEAD — a child's recovery step
  (`git checkout origin/<branch>`) can leave the SHARED repo checkout detached.
  Restore with `git checkout <branch>` and confirm `git status -sb`.

## Pitfalls

- Do not spawn before confirming the work exists and the targets are independent;
  worktrees and children for a merged or misattributed PR are wasted setup.
- Do not let a child post to GitHub or commit — half-finished or duplicated posts
  from a child you can't see are worse than posting yourself from consolidated
  findings.
- Do not report a child's self-claimed test pass without the honest
  pass/fail/blocked signal; a detached worktree that can't build will produce a
  fabricated green if the child is told to "confirm tests pass" unconditionally.
- Do not conclude a slow child is doing useful work: a stale transcript with
  findings already compiled means stuck-on-emit — stop it and salvage.
