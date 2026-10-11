# Planner brief — <feature/fix> edge-case smoke suite  (dispatch to DEEP tier)

You are the TEST PLANNER. Output = one suite spec file. Do NOT run the emulator, edit app code, or commit.

## Inputs
- Repo root + AGENTS.md / conventions file to read first.
- Fix under test: commit sha, file:line, the guard/logic it adds, the bug it fixes. Ask the planner to verify
  language-level semantics of the change (operator precedence, null paths) — not just behavior.
- Prior fix(es) on the branch whose behavior must not regress.
- Harness files to read (scenarios.yaml, harness.py, cdp.py, jev.py, project smoke skill).
- How to drive the input path on-device (e.g. fake poster APK + exact adb command), device serial to target ONLY.

## Deliverable: <plans>/<suite>.md
1. Risk analysis. Expected outcome per case derived from CODE (cite file:line). Spec silent -> EXPECTED=UNSPECIFIED + what to observe.
2. Ordered, self-contained scenarios a SMALL model can execute: id, purpose, reset/preconditions, exact steps and inputs
   (incl. NBSP/unicode), waits, hard DOM asserts using selectors verified to exist in src, expected numbers,
   "if FAIL: likely cause + file:line". vitest layer for anything not emulator-drivable.
3. Minimal harness extensions needed (new nav ops / code_assert ops / poster extras / OS support). Prefer code_assert over Jev.
4. Concrete YAML for new scenarios in the existing format.

Return to parent ONLY: file path + <=8-line summary (scenario count, top risks, any sign the fix itself is wrong).
