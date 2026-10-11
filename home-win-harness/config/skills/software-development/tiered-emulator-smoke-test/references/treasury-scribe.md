# Treasury Scribe notification smoke suite

Repo C:/Users/molna/VSCodeRepos/treasury-scribe (Windows git-bash; also macOS).
- Plan (deep): .maestro/smoke/plans/notif_group_summary_suite.md (risks, oracles, file:line).
- Suite: .maestro/smoke/notif_scenarios.yaml. One JSON object per line, with hints. NG01-NG18 and NG21 run on device; NG19 and NG20 are vitest. NATIVE-Q (Kotlin queue/mask unit gate) is NOT_RUN: there is no JVM test harness yet.
- Runner: .maestro/smoke/notif_runner.py (`--validate`, `--list`, `--only`, `--tag`, `--no-vitest`); tests are in test_notif_runner.py.
- Poster fixture: .maestro/smoke/fixtures/poster (Post.java: post/cancel/cancelAll/dump, fixed id, group, summary, `~EMPTY~` sentinel for empty title/body, handles onNewIntent; it logs a `TSPOSTER {json}` confirmation with a nonce and the native flags/postTime). The runner reads that confirmation with `logcat -d -v raw -s TSPoster:I`.
- Known verdicts on HEAD 12c2180 / API 35: NG16 and NG17 FAIL (known_red: the startup active-notification snapshot in NotificationListenerPlugin.kt has no summary filter). NG21 FAIL (known_red: OTP-redacted payload is persisted; fix = redaction guard that drops the sentinel body before persist, then assert 0 rows and clear known_red). NG15 BLOCKED (OS keeps the summary flag on a same-id update; to test the transition, cancel(id) between the two posts so the repost is fresh). NG01 carries the suite's only Jev noul.
- `npx tsc --noEmit` has existing errors unrelated to this fix (DashboardPage, SplitTransactionModal, RevolutImportService). Report them as a pre-existing gate failure, not a regression. Build and install both packages (com.revolut.revolut and com.treasury.smokeposter.other) with `bash .maestro/smoke/fixtures/build_poster.sh`. It borrows the app's android/ gradle wrapper.
- Executor brief: .maestro/smoke/plans/EXECUTOR_group_summary.md (dispatch the quick tier with "read it, authoritative").
- Env: `export PATH=/c/Users/molna/scoop/apps/nodejs/current:$PATH; source .maestro/smoke/android-env.sh` (OS-aware, sets ANDROID_SERIAL=emulator-5554). Python: C:/Users/molna/AppData/Local/hermes/cache/scratch/smokevenv/Scripts/python.exe (has pyyaml and websockets).
- AVD: Pixel_6_Pro (API 35). Boot command: `emulator -avd Pixel_6_Pro -no-snapshot-load -no-boot-anim -gpu swiftshader_indirect`.
- Autogroup evidence: `dumpsys notification --noredact` shows the record `tag=ranker_group flags=...GROUP_SUMMARY|AUTOGROUP_SUMMARY` under pkg com.revolut.revolut once 4+ ungrouped notifications are posted.
- Legacy FR UI harness (.maestro/smoke/harness.py + scenarios.yaml) is separate; on Windows it still needs the git-bash patch for cdp._adb.
- To add a scenario: append a line to the YAML. The first nav step must be reset_app. Use only ops the validator knows, and NBSP-grouped amounts.
