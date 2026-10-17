---
name: stack-migration-planning
description: "Use to plan an app rewrite onto a new framework/stack."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [planning, migration, rewrite, architecture, capacitor, maui]
    related_skills: [change-integration-analysis, plan]
---

# Stack / Framework Migration Planning

Write the implementation plan to rewrite an existing app onto a different tech stack, usually
modeled on a sibling "reference" repo. Output is a committed plan document, not code. Execution
happens later, gated on the user's trigger.

## When to use
- "Rewrite repo X into stack Y" / "make it like repo Z" / "migrate off framework F".
- Any task where the deliverable is a migration/rework PLAN, phased for later execution.
Not for: comparing a plan against open PRs (use change-integration-analysis); normal feature work.

## Always-on rules (every migration plan)
- VERIFY THE REFERENCE REPO'S ACTUAL STACK before planning — read its package.json /
  build.gradle / *.csproj / pubspec.yaml, never trust its name or the user's label. A repo the
  user calls "native Android" can in fact be React+TS+Capacitor (a WebView hybrid); the
  `android/` folder is just Capacitor's generated shell. A wrong stack premise invalidates the
  whole plan. If the label and reality disagree, STATE the mismatch and ask which they want
  before writing the plan — the two readings often mean opposite architectures.
- Match the TEST METHOD to the real framework. DOM-based CDP/JEV testing needs a WebView DOM
  (Capacitor/Cordova); .NET MAUI, Flutter, and native Kotlin/Compose render native views with
  NO DOM, so a DOM test method cannot run against them. Pick the method after confirming the
  framework, not before.
- Do the work on a dedicated branch + git worktree based off the integration branch (e.g.
  `develop`), not in the main checkout. Keep the main checkout clean.
- Commit regularly — after every phase and every green gate — with Conventional Commits, so any
  phase is independently revertible. Never commit a red gate.
- Resolve ambiguous scope with the user BEFORE writing the plan around it; do not invent
  requirements. When the user says "wait for my trigger," write/revise the plan and STOP — do
  not start scaffolding or implementation.

## Procedure

### 1. Audit the SOURCE app — full feature inventory to preserve
Read the current app's entry points, data layer, models, services, and platform-specific code.
Build a table: feature → current location → keep/change/fix. Capture exact behavioral rules
(ordering, defaults, validation, edge cases) that must survive the rewrite — these are the
acceptance criteria. Note which features do NOT port cleanly to the target (flag them early).

### 2. Model the TARGET stack from the reference repo
Read the reference repo's manifests (confirm the real stack, per always-on rule), its
ARCHITECTURE.md / AGENTS.md / conventions file, and one representative file per layer. Capture:
layer boundaries, data-layer choice, state pattern (hooks vs MVVM etc.), test strategy, naming
and style conventions, and the build/test/lint gate commands. The plan's conventions section
mirrors these.

### 3. Map source features onto target layers
For each preserved feature, name the target file(s) and the behavioral rule to replicate. Call
out features that need a different mechanism in the new stack (see the WebView-widget pitfall).

### 4. Write phased steps, each ending on a green gate
Order: scaffold → data layer (TDD) → services (TDD) → hooks/state (TDD) → UI → native shell/
platform bits → behavioral smoke test → remove old stack + docs. Each phase states its files,
tests-first where applicable, and the gate (`test` + `build` + typecheck). Commit per phase.

### 5. Pin DATA backward-compatibility when user data must survive the rewrite
If the user has exported data (or an on-device DB) from the OLD stack that they will re-import
into the new one, the plan MUST guarantee a lossless round-trip. Reverse-engineer the exact
legacy serialization format from the source code (serializer options + model field order), not
from guesswork: e.g. System.Text.Json with no naming policy emits PascalCase keys in
declaration order with ISO-8601 DateTimes and null for absent nullables. Record the exact
format, the legacy→new field mapping, and the import semantics to replicate (order, id reset).
Make the new importer TOLERANT of both key casings so old files and the app's own future
exports both load. Write a reference fixture under tests/fixtures/ and require import tests
against it. If you CANNOT run the source stack to produce a real sample (toolchain absent),
say so plainly in the plan, mark the fixture as hand-derived, and require validation against
the user's ACTUAL exported file before they rely on it — never claim round-trip success on a
hand-built fixture alone.
- A real export reveals encoding quirks a hand fixture misses: System.Text.Json escapes `+`,
  `<`, `>`, `'`, `&`, and ALL non-ASCII as `\uXXXX` (JSON.parse decodes natively, so import
  needs no special handling), but a new-stack export via `JSON.stringify` emits raw UTF-8 — so
  round-trip tests MUST compare PARSED VALUES, never raw bytes. Also handle multiline (`\n`)
  fields and variable-length fractional seconds in dates.
- If the user's real export contains personal data or secrets AND the branch has a public
  remote, git-ignore the file (keep it on disk as a local-only import fixture) and verify with
  `git check-ignore` — never print its sensitive values. A credential in a committed test file
  leaks the moment the branch is pushed.

### 6. Review the finished plan for ambiguity before handing off
Score each phase's acceptance criteria with the `jev-team-roles` `ac_completeness` scorer
(TypeSafe JEV) — feed `{title, acceptance_criteria}` per phase; the lowest-scoring phases are
the under-specified ones (usually the behavioral UI/state phases) — rewrite those with crisp,
testable acceptance. The execute_code/python kernel does NOT inherit the shell env, so JEV
returns `jev_unavailable` until you load the key: `zsh -c 'source ~/.zshrc; printf %s
"$TYPESAFE_API_KEY"'` and set it in the subprocess env. Then do a manual cross-section sweep
(grep the plan for the OLD stack's names) to catch stale wording a decision pivot left behind.

### 7. Record decisions, open questions, risks, DoD
List open questions with a recommended default each. Risks table = risk → mitigation. DoD =
the original asks satisfied + all source features preserved + gates green + smoke test green +
docs updated. When the user picks an option (e.g. a widget strategy), EDIT the plan in place to
lock that decision and ripple it through every affected section — do not leave it as an option.

## Pitfalls
- A native home-screen WIDGET cannot be a WebView component. In a Capacitor rewrite, the widget
  stays native (Kotlin RemoteViews). It needs the app's data: either a shared real SQLite file
  (`@capacitor-community/sqlite`, widget opens it read-only) or a JSON snapshot bridged to
  SharedPreferences on each mutation. Decide this explicitly — it shapes the data layer choice
  (real SQLite file vs sql.js-in-localStorage, which a widget cannot read).
- When the data layer changes (e.g. sql.js → `@capacitor-community/sqlite`), keep repository
  functions taking an executor/db as the FIRST arg behind a small interface, so tests inject a
  node sqlite driver and the app injects the Capacitor plugin — same code, two backends.
- Reverting superseded in-progress edits: when the user pivots mid-task, `git checkout --` the
  touched tracked files and delete new untracked files BEFORE starting the new direction, so the
  branch doesn't carry dead work.
- `dotnet` / MAUI build needs the .NET SDK + `maui-android` workload installed; a mac with only
  the Android SDK + JDK cannot build MAUI. Confirm the toolchain exists before promising a build.
- When choosing a replacement UI library (swipe, drag, etc.), confirm it targets the actual
  runtime: a Capacitor WebView runs react-dom, so React NATIVE libraries don't apply — search
  for web-React packages. Verify the pick supports the SPECIFIC behavior the requirement needs
  (e.g. react-swipeable-list exposes leading/trailing actions, so a left-handed user gets the
  delete on the LEFT via leadingActions). Note staleness/peer-version risk and name a concrete
  fallback (hand-rolled behind a stable component boundary) so the swap is a drop-in later.
- When execution will be a subagent SWARM (fresh-context children): write the plan AS the single
  source of truth and add a short execution-model section — dispatch prompts stay SHORT and say
  "read <plan path> (authoritative) first" (big inline briefs time out the stream); name each
  task's exact owned files + acceptance + green-gate commands; keep dependency-chained layers
  (data→services→hooks→UI) SERIAL and only parallelize FILE-DISJOINT clusters in their own
  worktree+branch (npm ci per worktree), merged `--no-ff`. A child cannot ask the user questions
  — it must stop and report on real ambiguity, not guess.
