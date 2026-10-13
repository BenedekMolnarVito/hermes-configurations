---
name: change-request-orchestrator
description: "Use when a change request (new feature / behaviour) needs multi-agent orchestration. Mirrors bugfix-orchestrator but swaps root-cause debugging for design+investigation, and greenfield branch/commit conventions."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [multi-agent, orchestration, change-request, feature, greenfield, hub-and-spoke, subagent, tdd]
    related_skills: [bugfix-orchestrator, synthesis-agent, jev-decisions, jev-engineering, android-webview-jev-testing, tiered-emulator-smoke-test, change-integration-analysis]
---

# Change-Request Orchestrator Skill

## Overview
This skill defines a repeatable, semi-deterministic workflow for executing
**change requests** (new features / behaviour changes) with full multi-agent
orchestration. It is the change-request twin of `bugfix-orchestrator`: the same
hub-and-spoke routing, parallelism, synthesis gates, and verification rigor, but
Stage 2 is *Investigation & Design* (no bug to root-cause) and the git/commit
conventions follow feature-request shape (`feat/<slug>`, `feat(<scope>): …`) per
the repo's `AGENTS.md`.

Each subtask is delegated to a subagent with fresh, isolated context, and the
**synthesis-agent** skill condenses results back to the orchestrator via a
structured handoff packet.

## Input Parameter
- `change_request` (string): the fixed-requirement / feature to implement,
  verbatim. May include acceptance criteria.
- `repo_context` (string): working directory + key spec files
  (`AGENTS.md`, `change_reqs.md`, `.github/copilot-instructions.md`,
  `docs/ARCHITECTURE.md`, `docs/BUSINESS_LOGIC.md`, the schema in
  `src/data/DatabaseService.ts`).

## Architecture (Treasury Scribe)
```
Capacitor Plugin (Kotlin)        -> listen Revolut notif, forward TS via event
  ↓
NotificationServiceCore (TS)     -> validate pkg, regex parse amount/currency, build Transaction
  ↓
IngestionService (TS)            -> dedup -> persist -> auto-soft-delete -> auto-tag (FIXED order)
  ↓
Repositories (TS)                -> all SQLite, prepared stmt, eager JOIN, IsDeleted=0 default
  ↓
React hooks + components         -> useTransactions / useEditTransaction / useDashboard own screen state
```
All business logic lives in TS and is unit-tested with a real in-memory sql.js DB.
The Kotlin plugin is a thin forwarder. Do NOT change the Kotlin layer unless the
spec explicitly demands it.

## Workflow Stages

### Stage 1: Planning & Branch Setup
- Create feature branch from `develop`: `feat/<slug>` (NOT `feat/bugfix/<slug>`).
  PR base = `develop`. Never branch from `main`.
- Spawn a **planner** subagent that decomposes the change request into an
  ordered task list and a small design, balanced for tech + UX, verifiable
  against the repo's Definition of Done (`AGENTS.md` §DEFINITION OF DONE).
- Identify file ownership / touchpoints; flag tasks that share files
  (must stay serial) vs file-disjoint (can parallelise).
- Confirm no dependency on `change_reqs.md` brainstorm ideas that are explicitly
  gated ("Do NOT change or commit anything yet, wait for user trigger"). If the
  CR is a brainstormed idea not yet promoted to a fixed requirement, STOP and
  escalate to the user instead of implementing.

### Stage 2: Investigation & Design  (replaces "Systematic Debug")
For greenfield work there is no root cause; instead, map the existing lifecycle so
the feature hooks into the correct seam with minimal blast radius.

- Split suspects into **file-disjoint, read-only clusters** and delegate one
  investigation subagent per cluster. Disjoint file sets let them run in parallel
  with zero merge risk. Suggested clusters for soft-delete/undelete-type work:
  - **Repository/DAO layer** — `src/data/TransactionRepository.ts`: every site
    that reads or writes the `IsDeleted` column; confirm there is no undelete mutator
    and whether `getTransactionById` already returns soft-deleted rows (it does —
    so Edit can already load a deleted txn by id).
  - **Ingestion/auto-soft-delete logic** — `src/services/IngestionService.ts`:
    `findSoftDeletedMatch` + `softDeleteTransaction` interactions; design where
    an undelete must survive / not be immediately re-soft-deleted on next
    notification.
  - **Edit screen + hook** — `src/components/EditTransactionPage.tsx`,
    `src/hooks/useEditTransaction.ts`: how the page loads by id, where a button
    would live, how it would call back into the hook + repository + navigate.
- **Forbid edits in this stage** — read-only only.
- Each subagent returns: existing soft-delete touchpoints, gaps/confirmations,
  and a concrete design recommendation for the undelete path (function name,
  signature, hook method name, UI test id).
- **MANDATORY: invoke synthesis-agent** to condense findings into a handoff packet
  before any implementation delegation.

### Stage 3: Implementation
- Delegate **fix subagents** per file/area. File-disjoint = parallel; shared
  files = serial within one cluster. Each cluster may use its own git worktree
  + branch (`npm ci` per worktree; `node_modules` is not shared), merged back
  with `--no-ff` to keep zero conflicts — or, for a single small feature, a
  shared branch is acceptable if files are disjoint.
- Conventional commit message: `feat(<scope>): <imperative>`.
- Each subagent implements the feature **and** adds/updates tests (TDD red →
  green is preferred; tests must live next to existing test files under `tests/`).
  Follow repo conventions exactly:
  - `db: Database` as first param; fresh in-memory DB per test
    (`beforeEach initDatabase`, `afterEach db.close`).
  - `make*` fixture factories; override only what the test cares about.
  - Explicit columns, `?` binds, `WHERE IsDeleted = 0` default for list queries;
    `withComputedProps()` re-attaches getters on DB fetches.
  - Inline `CSSProperties` dark theme (`#121212`); `data-testid` for the new
    button (`btn-undelete`).
- Run **typecheck + build + unit tests** after each fix batch.
- **MANDATORY: invoke synthesis-agent** after each fix batch to produce a handoff
  packet before the next delegation decision.

### Stage 4: Verification
- Run the full suite: `npm run test` (all green, no regressions).
- Run build: `npm run build`.
- Run typecheck: `npx tsc --noEmit`.
- Attribute-gate failures: typecheck/build errors in files outside
  `git diff --stat` are pre-existing — note them, do not chase them as
  regressions. Prove pre-existing with `git stash` + rerun of the exact failing
  test (see Lessons Learned).
- Coverage gate: new behavior = new test; coverage ≥ 95 % line+branch hold.

### Stage 5: UI Smoke Test (Emulator + Live Device When Available)
- Delegate to the **android-webview-jev-testing** skill subagent (Maestro + CDP).
- Run the Maestro smoke suite on the emulator; when the user has a connected
  phone (POCO F5), run the same suite live on-device as a second pass.
  Emulator = repeatability; live device = OS/OEM behaviour.
- Capture DOM dumps, screenshots, `report.json`.
- Behavioral scenario = a new `.maestro/` flow (not `scenarios.md`).
- **MANDATORY: invoke synthesis-agent** to condense smoke-test results.

### Stage 6: Commit & PR
- Commit with a Conventional Commit: `feat(<scope>): <imperative>`.
- Push branch, open PR against `develop` with summary + DoD check.
- PR auto when all acceptance met.

### Stage 7: Code Review (Fresh Context Subagent)
- Delegate code review to a **NEW** subagent with fresh context (no conversation
  contamination). Review uses PR-review standards (security, correctness,
  style, tests).
- The review brief **must** demand a re-entrancy / idempotency check adapted to
  feature interactions. For undelete specifically:
  > "Every new path that flips `IsDeleted` back to 0 — what happens when the
  > SAME item is delivered again by ingestion? Un-delete is idempotent (a no-op
  > on an already-active row), but time-window dedup is NOT idempotency: after
  > the dedup window expires, IngestionService step 3 (auto-soft-delete) will
  > re-soft-delete the undeleted row if a soft-deleted match still exists.
  > Verify the intended UX: should undelete clear the prior soft-deleted match,
  > or is re-suppression acceptable / by-design?"
- Review subagent returns: PASS or a list of required fixes.
- **Infra-blocked child (429 / provider error), ANY stage: ** mark DEFERRED,
  never absorb its work inline (no self-review for a rate-limited reviewer, no
  inline edits for a rate-limited implementer). A child killed mid-batch may
  have landed PART of its edits: run `git diff` first, write a salvage file
  listing "already applied / still missing" per file, and re-dispatch a NEW
  child with the same file-based brief + the salvage file path so it resumes
  without redoing work. Backoff 10 s, escalate tier once if the cheap pool
  stays congested (in practice: remap the congested tier's alias target —
  goal wording cannot move the classifier; see `hermes-model-tier-routing`)
  . Max 3 retries. If still blocked, land the verification evidence and leave
  the item as an explicit DEFERRED disclosure in the PR body and final report.
  For the Stage 7 review specifically, the fresh-context property is
  non-negotiable: an orchestrator self-review is NOT a substitute, and
  oneshot_spawn_budget exhaustion does not downgrade a review to inline
  self-review.
- **MANDATORY: invoke synthesis-agent** to condense review findings.

### Stage 8: Iterate Fixes from Review
- If review returns fixes, delegate fix subagents.
- Re-run verification + UI smoke test.
- Repeat Stage 7 until review PASS.
- **MANDATORY: invoke synthesis-agent** after each iteration batch.

### Stage 9: Final Verification & Merge Ready
- All acceptance met; tests green; build + typecheck clean; UI verified.
- Report final status to user (PR URL + summary + verification evidence).

## Delegation Rules
- Each subtask → a separate subagent (`delegate_task`). Route by complexity:
  - **quick**: factual lookups, file searches, simple verification, category
  - **moderate**: scoped implementation, routine edits, ordinary analysis
    (DEFAULT — what most impl subagents land on)
  - **deep**: ambiguous design, feature-interaction reasoning, idempotent
    correctness analysis
  - **long-horizon-complex**: sustained cross-system work
- **A synthesis-agent call MUST follow every subagent batch**, before the next
  delegation decision. The orchestrator reads ONLY the handoff packet.
- Big brief inline → stream timeout. Write the brief/rubric to a file in the
  worktree, dispatch a SHORT prompt ("read <path> first, it is authoritative").
  Subagent reports/diffs → file, not inline.
- Subagent contexts are ephemeral (discarded after report).
- Files are the unit of parallel safety: verify `git diff --stat` disjointness
  before parallelising; shared files stay serial inside one cluster.

## JEV-Based Decision Points
- Use **jev-decisions** for: classifying feature severity/impact (undelete =
  low-severity, high-utility, no security surface — reversible data-restoration),
  ranking implementation approaches (repository mutator first vs. hook-first).
- Use **jev-engineering** for: gating PR readiness, triaging test failures,
  confirming coverage adequacy on the new code paths.

## Spec Sources (this repo — no SPECIFICATION.md exists)
- `change_reqs.md` — active fixed-requirements + brainstorm/plan asks.
- `docs/ARCHITECTURE.md` — layers, schema, data-flow.
- `docs/BUSINESS_LOGIC.md` — user flows + smart behaviours.
- `.github/copilot-instructions.md` — authoritative code conventions, signatures.
- `docs/updates_2026_10_03/` — design + implementation plans from the brainstorm pipeline.
- **Spec silent → pick most maintainable, lowest cognitive load. Ambiguous → stop, resolve vs spec, do not invent. Behaviour not in spec = out of scope, flag not build.**

## Lessons Learned (change-request flavour)
- For greenfield work the investigation stage finds the **integration seam**,
  not a root cause. Map every read/write of the affected column (`IsDeleted`)
  before designing the mutator, so the undelete path closes the exact gap.
- Any mutator that flips a flag the ingestion pipeline also flips needs an
  **interaction re-entrancy check** (Stage 7): time-window dedup is not
  idempotency; a re-delivered item ages past the window and re-triggers
  auto-soft-delete. Decide by design whether undelete should clear the prior
  soft-deleted match, document it, and test it.
- Branch from `develop` with the `feat/<slug>` prefix (not `feat/bugfix/`) for
  new features; Conventional commit type is `feat`, not `fix`.
- Prove "pre-existing" with `git stash` + rerun of the exact failing test, not
  just file ownership — flaky tests and unhandled errors can masquerade as
  regressions in a small diff.
- Always verify on-device with Maestro/CDP, not just jsdom — the Edit screen
  uses a Capacitor dynamic import (`@capacitor/app`) that is a no-op under jsdom.
- Share-button removal must also clean up `useTransactions` (`shareExport`) and
  `App.tsx` injection. (Carry-over from repo history; re-scan touchpoints.)
