---
name: browser-regression-testing
description: "Use when turning web QA into deterministic browser tests."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [testing, browser, playwright, e2e, regression]
    related_skills: [dogfood]
---

# Browser Regression Testing

Turn validated UI scenarios into reproducible, low-output browser tests.

## When to Use

Use after exploratory browser QA finds stable scenarios worth preserving, when repeated manual DOM probing consumes too much context, or when a full-page flow needs deterministic fixture-backed regression coverage. Use exploratory QA first for unknown behavior; use this skill once the expected wire input and DOM outcome are known.

## Procedure

1. Freeze each scenario's wire input and observable DOM invariants. Prefer small JSON/NDJSON fixtures at the network boundary over live services, authentication, or model calls.
2. For full-page E2E flows, prefer standalone Playwright Test. Use a managed `webServer`, accessible role/label locators, auto-retrying assertions, one browser and worker, fixed locale/timezone/viewport, reduced motion, and trace/screenshot capture only on failure.
3. Intercept the application's real API route and fulfill it with fixtures. Block external traffic so missing interception fails rather than contacting a service.
4. Derive the allowed application origin from the configured base URL; never hardcode the default port. For allowed same-origin requests call `route.fallback()`, not `route.continue()`, because `continue()` can bypass a more specific fixture route.
5. Synchronize on the final rendered DOM target. Do not wait with fixed sleeps or transport controls such as a stop button; those can outlive the useful response.
6. Assert business invariants directly: exact formatted values, shared chart scales, totals, absence of forbidden elements/classes, and computed-style equality when semantic neutrality matters.
7. Keep live-backend tests in separate `*.live.spec.*` files behind an explicit environment flag. They are integration checks, not deterministic regression gates.
8. Run the suite with concise output. A successful run should show test names and a pass count; inspect retained traces only on failure.

## Local-only evaluation gate

When the user wants to evaluate a proposed suite before Git adoption:

1. Add every proposed config, test, fixture, report, and artifact path to `.git/info/exclude` before creating or installing anything.
2. Install dependencies without modifying tracked manifests or lockfiles; for npm use `npm install --no-save --package-lock=false <package>`.
3. Put setup instructions and the per-clone exclusion warning in an excluded local README.
4. Verify after every run with both `git status --short --untracked-files=all` and `git check-ignore -v <every path>`.
5. Do not commit or push until the user explicitly adopts the suite.

`.git/info/exclude` is checkout-local and does not survive a fresh clone. Repeat the exclusions before copying the suite into another checkout.

## Pitfalls

- Match the stable semantic portion of generated accessible names; exact labels containing row counts or incidental prose create brittle failures.
- If development rendering creates duplicate equivalent nodes, first verify they represent the same turn, then scope to the latest message/card or use `.last()` locally. Do not weaken every assertion.
- Include all generated artifact directories in exclusion checks; source files may be hidden while reports or traces remain stageable.
- Keep fixture fidelity at the transport boundary: use the same content type and event envelope as production so parsing and reducer behavior remain exercised.
