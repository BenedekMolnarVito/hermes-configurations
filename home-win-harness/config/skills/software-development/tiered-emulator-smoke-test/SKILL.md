---
name: tiered-emulator-smoke-test
description: "Use to smoke-test a fix on emulator via tiered subagents."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [testing, android, emulator, capacitor, cdp, jev, delegation, smoke, regression]
    related_skills: [android-webview-jev-testing, typesafe-ai, test-driven-development]
---

# Tiered emulator smoke test (plan deep -> harden -> execute quick -> brief)

Verifies a fix on an Android emulator with replayable, DOM-driven (CDP, no screenshots)
scenarios. Expensive reasoning happens once: a high-tier planner designs the suite. A small
lowest-tier executor then replays it mechanically and returns only a compact verdict that
workers can act on.

## When to Use
- "Verify latest fix via smoke test in emulator", regression check of a native/WebView change.
- Any time an on-device test should be delegated to a small model.
- Not for pure unit logic (write vitest) or native-only UIs (DOM tooling won't see them).

## Pipeline (parent orchestrates; every brief is a FILE, dispatch prompt is short)
1. Context (parent, inline): `git show HEAD`, find the harness, check devices. If a physical
   phone is attached, pin `emulator-5554` everywhere (env ANDROID_SERIAL + `-s`).
   Boot the AVD in background and rebuild the APK IN PARALLEL with planning (a native fix
   makes the installed APK stale; compare APK mtime vs `src` and `android/app/src`).
2. Plan (subagent, task text phrased as deep risk/correctness analysis -> deep tier):
   brief file = fix diff summary, harness files, fixture tools, safety rules, deliverable path.
   Output: risk analysis + self-contained scenarios (exact payloads, state reset, hard DOM
   oracles, `If FAIL: file:line` hints, EXPECTED=UNSPECIFIED where the spec is silent) +
   harness-op requirements + proposed YAML. Planner must justify every expectation by
   source line, never guess.
3. Harden (scoped worker, moderate tier; or parent inline if small): implement the ops,
   validator, and pure-logic unit tests. Then SELF-CHECK on the device yourself with ONE
   scenario per distinct fixture shape: plain child, explicit summary, empty title/body,
   back-to-back same-id updates, emoji/non-BMP text, autogroup, and restart. Covering one
   example of each shape is enough. Bugs in the fixture's transport layer only show up for a
   specific payload shape. A small executor will just report them as ERROR without fixing
   anything, so they cost a whole extra dispatch.
4. Executor brief file (small-model proof): numbered steps, exact commands, env line repeated per
   call, chunked runs under the 600s terminal cap (`--only ... --tag cN`), retry policy
   (ERROR once, never FAIL/BLOCKED), verdict glossary, and a fixed result template. Forbid
   edits, fixes, and commits. Every number must come from tool output. Put `set -o pipefail`
   before every `cmd | tail` gate, because otherwise the reported exit code is tail's.
   If a scenario uses Jev, add a key-presence check that never prints the key.
5. Execute (subagent, task text phrased as "run commands and report pass/fail" -> quick tier).
6. Parent: spot-check the claims against the report JSON on disk (child output is a
   self-report), then relay the brief result. FAIL blocks go straight to fix workers.
   Triage first: if ERROR verdicts cluster on one fixture shape, the harness is broken.
   Fix it, self-check that shape, delete the stale out/ reports, and re-dispatch the
   executor. Never relay harness ERRORs as app findings.

## Verdict contract (runner must implement)
PASS | FAIL (app wrong vs oracle) | ERROR (harness/precondition broke, not an app verdict) |
BLOCKED (env can't exercise the case, e.g. OS posted no autogroup summary) | NOT_RUN.
`known_red` = planner predicts FAIL on HEAD; FAIL confirms the bug, PASS = "unexpectedly PASS".
The runner fails closed: unknown ops/keys -> ERROR, Jev error or missing answer -> ERROR,
and a tap on a missing element -> ERROR.

## Treasury Scribe instance (proven, Windows + API 35)
See references/treasury-scribe.md for files, commands and the 21-scenario notification suite.

## Pitfalls
- Android 15+ (API 35) SENSITIVE-NOTIFICATION REDACTION: a payload with a contiguous 4+ digit
  number looks like an OTP. Listeners without RECEIVE_SENSITIVE_NOTIFICATIONS then get
  title=<poster app label> and body "Sensitive notification content hidden". Identical redacted
  payloads also dedup into one row. Use real-format NBSP thousands grouping ("1\u00a0000\u00a0Ft")
  in fixtures. The validator rejects 4+ digit payloads unless the scenario id contains "otp".
- Windows PATH BLOAT: the Hermes terminal keeps env between calls, so a brief that says "export PATH=X:$PATH
  every call" (or a non-idempotent env script) grows PATH past cmd.exe's ~8191-char limit. Then
  `npm run` scripts fail with "'vitest'/'vite' is not recognized" even though node_modules/.bin exists.
  Make env scripts dedupe PATH and have the brief echo PATH_LEN (<8000), so this reports as an env ERROR
  instead of an app FAIL.
- `cmd | tail` hides the exit code: an executor reported "vitest exit 0" over 2 unhandled errors. Put
  `set -o pipefail` in every brief gate. Treat vitest "Errors N" as failing even when all tests pass.
- `adb shell am start --es key ""` silently drops the empty value and misaligns the extras that follow
  (summary flag lost). Send a non-empty sentinel (`~EMPTY~`) and decode it to "" in the poster.
- Re-launching an already-running poster Activity delivers to onNewIntent, not onCreate. Handle
  both, or the second post is never made ("poster post not confirmed").
- API 35 keeps FLAG_GROUP_SUMMARY when the same notification id is re-posted as a child: detect it by comparing the requested flag against the actual native flag and report BLOCKED (platform behaviour), not ERROR or FAIL. To TEST the transition instead of blocking on it, cancel(id) between the two posts — cancel clears the OS record so the repost is fresh and carries the requested flag. Never auto-cancel inside the poster fixture: same-id updates without cancel are what the dedup/update scenarios depend on.
- RECEIVE_SENSITIVE_NOTIFICATIONS is signature/role-level: `pm grant` throws SecurityException and a manifest request buys nothing for a store app, so OTP redaction cannot be bypassed on-device. The product fix is a redaction guard, not a permission: drop payloads whose body is the redaction sentinel before persisting (ingestion layer plus native toNotificationData as defense in depth), then assert the drop (0 rows) in the scenario and clear its known_red flag.
- APK freshness: exclude android/app/src/main/assets (rewritten by `cap sync`) from the `find -newer` check.
- Delegation can die mid-task (provider 402/credit limits). Check `git status` for partial artifacts
  and finish them yourself; don't blindly re-dispatch.
- Python subprocess `bash` on Windows = WSL bash. Call `adb` directly via argv lists. Bash in
  scripts sees TMPDIR=/tmp, so derive scratch paths from LOCALAPPDATA.
- Don't `adb forward --remove-all`. Remove only your own port. Pick the WebView socket by the app's
  PID (`pidof`), not the first socket.
- Read rows from the LIVE DOM (card face children), compare as order-independent MULTISETS with
  exact NBSP. Never use body-text substring search. Await a stable match, then watch 3 more
  seconds for late extras.
- Per-scenario reset: cancel poster notifications, `pm clear`, regrant POST_NOTIFICATIONS and
  `cmd notification allow_listener`, deviceidle whitelist, wait for the UI, assert zero rows.
  A broken baseline = ERROR.
- PyYAML decodes JSON-style `\ud83c\udf7f` escapes into lone surrogates, and UTF-8 encoding
  then fails. Normalize loaded specs with
  `s.encode('utf-16','surrogatepass').decode('utf-16')`.
- force-stop unbinds the listener. Record that it rebound, else BLOCKED (otherwise a restart
  scenario passes vacuously).

## Verification
- `python -m unittest test_notif_runner` OK and `notif_runner.py --validate` VALID before dispatch.
- Self-check scenarios PASS on device before handing off to the quick executor.
- The executor's final answer matches `out/notif/report_c*.json` on disk.
