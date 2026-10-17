---
name: change-integration-analysis
description: Compare planned work with active branches before coding.
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Git, Pull-Requests, Planning, Integration]
    related_skills: [github-code-review, plan]
---

# Change Integration Analysis

Compare planned work with open branches or pull requests before implementation. The output identifies textual overlap, semantic dependencies, incompatible designs, and the lowest-risk branch strategy.

## When to Use

- A planned feature may overlap an open pull request.
- Two tickets affect the same subsystem, tests, prompts, or evaluation data.
- The user wants to know whether work belongs in one branch, separate branches, or a stacked branch.
- A plan was written before a prerequisite branch changed the implementation model.

Do not use this as a full code-quality review or as permission to merge, rebase, commit, or push.

## Procedure

### 1. Freeze both comparison inputs

1. Read the complete implementation plan or ticket requirements; extract planned files, behaviors, tests, and verification expectations.
2. Fetch current pull-request metadata, head SHA, base SHA, changed files, commits, checks, and unresolved review state.
3. Record the current checkout branch, HEAD, and dirty state using the repository-mandated execution environment.
4. Compare immutable SHAs rather than moving branch names so later PR updates cannot silently change the evidence.

Completion criterion: both sides have an explicit SHA and complete file list.

### 2. Read the actual diff, not only the PR summary

1. Diff the PR head from the plan's base commit file by file.
2. Read full surrounding implementations for overlapping symbols; summaries often hide a changed execution model.
3. Inspect tests and ground truth alongside production code because they reveal the intended contract.
4. Locate exact lines in the PR head for consequential behavior and cite them in the report.

Completion criterion: every overlap claim points to an observed file, symbol, test, or dataset row.

### 3. Build three overlap maps

Classify each item separately:

- **Textual overlap:** both sides edit the same file or nearby hunk; estimate merge-conflict probability.
- **Behavioral overlap:** different files implement or test the same externally visible behavior.
- **Semantic dependency or contradiction:** one branch changes assumptions that make the other plan obsolete or wrong.

Compute the direct file overlap, but never use file count alone as the judgement. One changed helper can invalidate an entire planned architecture without sharing many files.

Completion criterion: each planned change is marked independent, complementary, duplicate, prerequisite-dependent, or contradictory.

### 4. Reconcile plans against proven runtime behavior

1. Prefer executable evidence from the open branch's tests and verified data over a stale planned API shape.
2. Distinguish business intent from physical execution. A request may route through a named hierarchy concept while the tool must execute through expanded leaves or a flat fact dimension.
3. When a prerequisite branch proves an API path returns false zeroes, wrong keys, or non-reproducible slices, remove that path from the downstream plan instead of attempting to merge both implementations.
4. Preserve independently verified ground truth. Add downstream routing assertions around it; do not restore old values or rewrite evidence to fit the planned design.
5. Identify which planned tasks should be deleted, rewritten, or retained after the prerequisite lands.

Completion criterion: the recommendation includes concrete plan edits, not only a conflict warning.

### 5. Choose the branch strategy

Use this decision order:

1. **Separate sequential branches:** choose when objectives are independently reviewable but one supplies infrastructure or corrected ground truth for the other. Merge the prerequisite first, then rebase the dependent branch.
2. **Stacked branches:** choose when work must start before the prerequisite merges. Base the dependent branch on the prerequisite head and open/review only its incremental diff; rebase onto the merged base later.
3. **Single combined branch:** choose only when changes are inseparable, neither can be validated independently, and splitting would duplicate implementation or leave either branch knowingly broken.
4. **Independent parallel branches:** choose only when there is no semantic dependency and overlap is limited to mechanically reconcilable edits.

Do not recommend combining merely because several files overlap. Review scope, rollback boundaries, CI attribution, and ownership matter more than conflict avoidance.

Completion criterion: one strategy is recommended, alternatives are ranked, and the reason addresses both merge risk and reviewability.

### 6. Report in decision-ready form

Present:

1. Comparison basis: branches, immutable SHAs, PR state, and check status.
2. Directly overlapping files.
3. Similar or reusable work.
4. Semantic conflicts or obsolete planned assumptions.
5. Likely textual merge-conflict areas, ranked high/medium/low.
6. Work that remains independent.
7. Judgement: combine, sequence, stack, or proceed independently.
8. Exact next steps, including required plan revisions.

State skipped or blocked verification plainly. Do not claim a PR is ready merely because available CI checks passed; mention unchecked required evaluations or reviews.

## Pitfalls

- Read production and tests together before proposing conflict resolution; tests often encode a newer execution contract than the plan.
- Do not equate business hierarchy routing with hierarchy-axis execution; the concept can be resolved through one hierarchy while the query runs against fact leaves.
- Do not implement a planned helper extension before checking whether another branch deliberately changed that helper's mode; widening the stale path can undo a verified fix.
- Compare evaluation rows by stable row ID and meaning, not line number, because large JSON strings make nearby edits conflict easily.
- Rebase after the prerequisite merges instead of manually recreating its changes; recreating verified infrastructure invites drift.
- Keep separate tickets in separate PRs when they retain independent review and rollback value, even if they use a stacked development branch.

## Verification Checklist

- [ ] Immutable base and head SHAs recorded
- [ ] Full changed-file lists compared
- [ ] Every planned file classified
- [ ] Same-hunk and semantic conflicts distinguished
- [ ] Production behavior checked against tests and ground truth
- [ ] Obsolete plan steps explicitly identified
- [ ] Required evaluation or review gaps disclosed
- [ ] Branch strategy and fallback strategy recommended
- [ ] No branch mutation performed without permission
