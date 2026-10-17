---
name: web-ui-regression-testing
description: "Use when converting browser QA into deterministic tests."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [testing, browser, playwright, e2e, regression]
    related_skills: [dogfood]
---

# Web UI Regression Testing

Convert validated browser scenarios into fast, reproducible test suites that run without repeated agent-driven browser inspection or live-model variance.

## When to Use

- Repeated manual browser or CDP checks should become regression tests.
- An agent-backed UI needs deterministic coverage without invoking the live model.
- A browser suite must be trialed locally before repository adoption.
- Existing E2E output is too verbose or expensive to interpret repeatedly.

## Procedure

1. **Freeze the scenario contract.** Record only observable outcomes: accessible role/name, displayed values, classes or computed styles, alert absence, and allowed view transitions. Keep semantic assertions separate from implementation details.
2. **Choose the test layer.** Use standalone Playwright Test for full-page flows and Vitest Browser Mode for isolated component tests. For agent-backed UIs, default to Playwright with browser-boundary API interception; keep the live stack as a separate optional integration test.
3. **Capture minimal fixtures.** Store the smallest real response shape that reproduces each scenario. Prefer protocol-native fixtures such as NDJSON event streams over application-internal mocks so parsing, reducers, and rendering are exercised together.
4. **Make execution deterministic.** Use one browser and worker initially, fixed locale/timezone/viewport/color scheme, reduced motion, blocked service workers, and a strict dedicated port. Start the app through Playwright `webServer`; fail if the port is occupied rather than silently selecting another.
5. **Block unplanned network traffic.** Derive the allowed origin from the configured base URL; never hardcode its port. Register a catch-all route that aborts foreign origins and calls `route.fallback()` for same-origin requests so more-specific fixture handlers still run. `route.continue()` bypasses later handlers and can silently defeat interception.
6. **Use web-first DOM assertions.** Prefer role/name locators and auto-retrying assertions. Wait for the scenario's rendered result, not sleeps, transport controls, or loading-button disappearance. Scope to the latest turn/card when development mode can render duplicate trees. Avoid exact accessible-name templates when only a stable title prefix is contractual.
7. **Keep output cheap.** Use a concise line reporter, traces/screenshots only on failure, no video by default, and no successful-run DOM dumps. A green run should be a short pass/fail report requiring no LLM interpretation.
8. **Separate deterministic and live suites.** The default command must need no credentials, backend, or LLM calls. Gate live tests behind an explicit environment flag and externally supplied base URL; live checks verify integration only and must not replace fixture-backed regression tests.
9. **Verify the suite itself.** Run it twice after synchronization or routing changes, then run the relevant unit tests and production build. Inspect failure traces only when needed.

## Local Evaluation Before Adoption

When the user wants to trial the suite before committing it:

- Put suite paths and artifacts in `.git/info/exclude`, not the tracked `.gitignore`; this keeps the experiment invisible only in the current checkout.
- Document that `.git/info/exclude` is per-clone and list the entries needed if files are copied elsewhere.
- Restore any tracked manifest, lockfile, README, or `.gitignore` edits made during setup. Install test dependencies locally without persisting lockfile changes when possible.
- Prove safety with both `git status --untracked-files=all` and `git check-ignore -v` for every config, test, fixture, report, and result path.
- Before adoption, remove the local exclusions, add the dependency/scripts/docs deliberately, regenerate the lockfile, rerun all gates, then commit.

## Pitfalls

- Do not repeatedly probe a stable scenario through interactive browser tools; encode it once and rerun the script because repeated DOM dumps consume context and introduce manual drift.
- Do not claim a fixture-backed suite tests authentication or the live backend; it tests the browser contract at the intercepted boundary.
- Do not use screenshot snapshots for financial text and semantics when DOM assertions are precise; screenshots are slower and more sensitive to harmless rendering changes.
- Do not infer completion from a stop/send control remaining mounted; assert the expected chart/table/result because UI chrome may persist after transport completion.
- Treat duplicate matching elements as a scoping problem, not a reason to disable strict mode globally; scope to the intended latest card or turn.
