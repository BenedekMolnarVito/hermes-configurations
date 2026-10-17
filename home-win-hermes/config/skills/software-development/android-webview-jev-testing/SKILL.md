---
name: android-webview-jev-testing
description: "Use to emulator-smoke-test a Capacitor WebView app via Jev."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [android, capacitor, webview, cdp, typesafe, jev, testing]
    related_skills: [typesafe-ai, computer-use]
---

## When to Use
Use when running DOM-driven visual/behavioral tests on a Capacitor (or Cordova)
Android WebView app and the TypeSafe Jev model is the decision-maker: extract
the real DOM over CDP, let Jev return a typed pass/fail verdict plus the next
action. Not for native Android apps (use uiautomator/Appium there).

# Android WebView behavioral testing with CDP DOM extraction + TypeSafe Jev

Pattern: browser-use's DOM-based agent loop applied to an Android WebView app.
Extract a distilled DOM snapshot over the Chrome DevTools Protocol, feed it to
TypeSafe's **Jev** System One model, and let Jev return TYPED judgments
(Noul = pass/fail probability, Choice = next action / target element). Code owns
the loop. No pixels, no OCR, no screenshots-as-ground-truth.

## When this applies
- App is Capacitor/Cordova (a Chromium WebView), NOT native Android.
- You need reliable, repeatable, agent-runnable behavioral assertions.
- JEV/TypeSafe is the decision model (key env var: `TYPESAFE_API_KEY`).

## Why NOT uiautomator or screenshots
- A Capacitor WebView's DOM is NOT exposed to the Android accessibility tree,
  so `uiautomator dump` and Maestro's hierarchy return EMPTY text for the app.
- Screenshots need OCR; a non-vision model burns minutes guessing pixels.
- CDP gives the real DOM directly: element text, roles, tap coordinates.

## Critical gotchas (cost real time if missed)
1. HOST CHROME HOLDS :9222. Desktop Chrome binds 127.0.0.1:9222 and you get
   its 404s, not the WebView. Forward to :9333. Check `lsof -nP -iTCP:9222`.
2. WEBVIEW SOCKET PID CHANGES. Socket is `webview_devtools_remote_<PID>` and
   the PID changes when the WebView respawns. RE-RESOLVE + re-forward on EVERY
   CDP call: `adb shell cat /proc/net/unix | grep -oE 'webview_devtools_remote_[0-9]+' | head -1`.
2b. STALE LOCAL FORWARDS SILENTLY HIJACK TARGETS. An old `adb forward
    tcp:9333` to the EMULATOR survives and the phone's forward to the same
    local port never binds — all CDP traffic then hits the emulator while
    every log claims the phone. Proven failure (UD1-UD6 'phone' run went to
    the emulator). Fix: `adb forward --remove-all` (then re-add per device)
    before EVERY run + VERIFY the bound target with a write-probe
    (eval-set localStorage `zz-probe`, read back) AND a screen-size check
    (emulator 412x892-class vs phone) before the first assert.
2c. VERIFY RESTORES AT CONTENT LEVEL, never file bytes. Decoded sqlite rows
    (python sqlite3 on the base64 blob) are ground truth: raw base64 file
    bytes differ by encoding, and LevelDB files rewrite on open. Byte-diff of
    `.b64`/leveldb files is a guaranteed false alarm.
3. CDP `/json` may 404 (Host-header protection) but `/json/list` and
   `/json/version` work once forwarded to the right socket.
4. Debug APK already exposes CDP. A release build needs
   `WebView.setWebContentsDebuggingEnabled(true)`.
5. App may chain STARTUP PERMISSION REDIRECTS (notification-listener access,
   battery-optimization exemption) that steal foreground. Grant via adb
   (`pm grant`, `cmd notification allow_listener`) or press Back to dismiss.
6. execute_code kernel does NOT inherit the shell env. Load the key with
   `zsh -c 'source ~/.zshrc; printf "%s\\0" "$TYPESAFE_API_KEY"'` and split on
   NUL (interactive `-i` injects stray chars; `${#VAR}` gives the true length).
7. CAPACITOR v8 Filesystem directory creation is broken on Android. `mkdir({path:"",
   directory:"DOWNLOADS", recursive:true})` throws "Directory at '/' already exists"
   when the dir is present, and `writeFile({directory:"DOWNLOADS", recursive:true})`
   fails with "Missing parent directory" because `getExternalFilesDir(DIRECTORY_DOWNLOADS)`
   resolves to a path whose parent doesn't exist and the plugin cannot create it. Fix:
   write to `Directory.EXTERNAL_STORAGE` with a subdirectory path and recursive:true,
   or `Directory.DOCUMENTS`, or skip Filesystem and call `Share.share({text: content})`
   for a text-only share. When on-device export is blocked by this, unit-test the JSON
   format instead of fabricating a green on-device result.

## Jev API (TypeSafe System One)
- `POST https://api.typesafe.ai/v1/systemone`, `Authorization: Bearer <key>`,
  model `jev-latest`. Body `{state, model, questions}`; `questions` ids are yours.
- Noul -> `{type:noul, instructions, criteria:{true,false}}`; answer `{noul:0..1}`
  = probability of yes. Use for the pass/fail VERDICT.
- Choice -> `{type:choice, instructions, criteria:{opt:desc,...}}`; answer
  `{choice, probabilities, confidence}`. Use for NEXT ACTION and to pick the
  TARGET ELEMENT (criteria keys = element indices, values = element text).
- Ask verdict + action in ONE request. Threshold in code: PASS if goal Noul
  >= 0.8, FAIL if < 0.3, else UNCERTAIN/escalate.
- Docs source of truth: https://docs.typesafe.ai/llms.txt (append .md to a path).

## The loop
1. Extract distilled DOM over CDP (interactive els + leaf text, center box).
2. Jev: `goal_reached` (Noul) + `target_element` (Choice over element indices).
3. If goal Noul >= threshold -> PASS. Else tap Jev's chosen element SEMANTICALLY
   via a CDP DOM `.click()` on the element whose innerText == target (prefer the
   smallest matching node = the real control), re-extract, repeat.

## Reference runner
Complete working runner: `scripts/jev_dom_runner.py`. Needs the `websockets`
pip package and an `android-env.sh` exporting JAVA_HOME/ANDROID_HOME/PATH for
adb+emulator. Proven 2/2 scenarios PASS unattended on a Capacitor budget tracker.

## Delegated smoke-test workflow (user's standard for "verify fix in emulator")
The user wants every emulator verification run this way, without being re-asked:
1. SCENARIOS FIRST, semi-deterministic: fixed nav steps + hard CDP-DOM asserts
   (testid/url/counts/js), Jev only for batched semantic yes/no. Never screenshots.
   Each scenario self-contained (preconditions/reset, exact inputs incl. NBSP,
   waits, exact expected values, "if FAIL look at file:line" hint) so a SMALL
   model can run and judge it without reasoning about the app.
2. EDGE CASES are mandatory, not just the happy path (for a notification fix:
   threshold counts, updates of same id, explicit vs auto group summaries, other
   packages, empty body, dedup, pending-queue path, prior-fix regressions).
3. Elaborate suite -> plan it with a DEEP-tier planner subagent that derives
   expected outcomes from code (cite lines; ambiguous = flag UNSPECIFIED, never
   invent). Then a moderate worker extends the harness/scenarios.yaml. The
   EXECUTOR brief must carry every UNSPECIFIED as an explicit build-time code
   lookup (const value, selector, window exposure, storage key) to resolve
   BEFORE driving — never left for the executor to guess mid-run. Brief
   templates: templates/planner-brief.md, templates/runner-brief.md.
4. EXECUTION goes to a QUICK/lowest-tier subagent: phrase the goal as simple
   verification ("run command, report pass/fail") so the router picks quick.
5. Only a BRIEF result returns to the main session: N/M pass + one block per
   FAIL with failing assertion, expected vs got, DOM-dump path, suspected
   file:line — enough for a worker to start fixing immediately.
6. Do independent prep (boot AVD, rebuild+install APK) in the main thread while
   the planner runs; write briefs to files and dispatch short prompts.

## Behavioral smoke-test workflow (Treasury Scribe, proven)
- The installed APK goes STALE: before testing a branch, check `find src android/app/src -newer <apk>` (native Kotlin/Java fixes live under android/app/src and are invisible to `find src`) and REBUILD (npm run build; npx cap sync android; cd android && ./gradlew assembleDebug) + `adb install -r -g` the fresh APK. The npm `android:run` hardcodes Windows gradlew.bat — use `./gradlew`.
- Maestro is NOT the DOM tool here: a Capacitor WebView's DOM is absent from the a11y tree, so Maestro assertions see nothing. Use Maestro only to boot/launch; do all behavioral assertions via CDP DOM + Jev (jev_dom_runner.py).
- Jev loop verdicts are noisy on multi-step nav: trust the DUMPED DOM over the Jev score. A UNCERTAIN/FAIL often just means the loop didn't reach the screen; a false PASS can happen when a lookalike control (e.g. a Default/Exception toggle in the Add modal) is mistaken for the target screen (Edit). Always confirm `url` + testids in the dumped DOM.
- Many features are DATA-GATED (tag cloud show-more needs >8 tags, edit/back needs a txn to edit). Seed via the app's OWN Add-Transaction modal over CDP: set React-controlled inputs with the native value setter + dispatched 'input' event (NOT el.value=), find fields by placeholder/data-testid. Submit auto-commits trailing tag text.
- NOT emulator-drivable, cover by unit tests instead: file export/import round-trips (Capacitor Share/Filesystem write + native file picker). Run the targeted vitest suites as supporting evidence; never fabricate on-device results.
- Notification ingestion IS emulator-drivable: adb can't spoof the poster package, but a throwaway APK whose applicationId IS the allow-listed package (com.revolut.revolut) can post real notifications. Template: references/fake-notification-poster.md (Activity takes base64 UTF-8 title/body extras so NBSP/newlines survive adb). Then `cmd notification allow_listener <app>/<app>.RevolutNotificationService`, post, read rows via CDP DOM. Posting 4+ notifications makes Android's GroupHelper post an AUTOGROUP summary under the SAME package (FLAG_GROUP_SUMMARY|FLAG_AUTOGROUP_SUMMARY); a listener that doesn't skip FLAG_GROUP_SUMMARY captures it as an empty row. Regression check: post >=4, assert row count == posted and no empty rows. Keep the poster's source IN THE REPO (e.g. under .maestro/smoke/) — the Hermes scratch dir is pruned after 24h idle, losing it.
- Any fix that re-polls the shade (cold-start drain, focus/resume drain, listener rescan) needs a persistent processed-identity guard OUTSIDE the SQL ±seconds dedup window — the shade is a snapshot, so every re-poll of a still-visible item mints a duplicate once it ages past the window. Key on stable shade identity (package/title/body/post time; genuine reposts carry a new post time), persist across restarts, TTL + cap the set, and record live-event deliveries too so later polls skip them. PITFALL: when a same-id notification is updated from summary to child, Android RE-TAINS the prior FLAG_GROUP_SUMMARY on the live record and the poster's flag-confirmation poll will refuse to match the new intent — a same-id repost looks like a harness ERROR/BLOCKED, not an app verdict. If a scenario needs a summary-to-child transition on the SAME id, INSERT a cancel (pm cancel <id>) between the two posts so the second notify() is a fresh record whose flag actually flips; do NOT make the poster auto-cancel before every post, that silently breaks same-id update/dedup scenarios that depend on the update path.
- Windows host: `bash` in Python subprocess resolves to System32 WSL bash, not git-bash; monkeypatch `cdp._adb` to use `C:/Program Files/Git/bin/bash.exe`. If a physical phone is also attached, set ANDROID_SERIAL=emulator-5554 (cdp.py calls bare adb) and pass `-s` everywhere so the user's real device is never touched.
- `npx cap sync android` rewrites android/capacitor*.gradle line endings: `git checkout --` them before committing.
- adb `input swipe` does NOT reliably trigger React swipe-to-delete handlers (they need a held drag). Prefer an in-DOM control or the repo/hook path over a synthetic swipe.
- Synthetic drags against sensor-gated libraries (dnd-kit PointerSensor/TouchSensor with a `delay` activation constraint) NEVER activate when the whole pointerdown/move/up burst is dispatched synchronously in one JS evaluation — space it with real time: pointerdown, sleep longer than the delay, several incremental moves with sleeps, then pointerup. No hold means no activation, and the harness will report 'no change' forever.
- When the app live-reorders during dragover (arrayMove on state), the dragged row ends up UNDER the pointer at drop, so a drop handler that treats `over.id === active.id` (or `over == null`) as 'no-op, skip persist' swallows nearly every real drop while the UI still shows the new order — a silent revert on next reload. The correct no-op test is snapshot comparison: record the id order on dragstart, persist on drop iff it differs. If on-device order never sticks but the DOM reorders and no errors surface, check this guard first.
- Resetting a data-gated suite between scenarios with `location.reload()` re-boots the app at the PREVIOUS scenario's final URL — if that is `/edit/<old-id>` and the reset just wiped the DB, the missing txn crashes the React tree (no error boundary), and every later pushState nav is inert while `location.pathname` still looks right. Reset with a HARD full navigation to a safe route (`location.href = location.origin + '/'` after removeItem) so React reboots; assert page render (a known testid) after reset, not just the URL.
- When no repo fn is exposed to `window` and the DB lives in WebView localStorage as base64 (e.g. `localStorage[key] = base64(sql.js db.export())`), do in-DB mutations (soft-delete, fixture rows) by pulling the base64, patching it with Python stdlib `sqlite3` (it opens sql.js exports directly), pushing the new base64 back, and reloading — a real storage-layer mutation; read it back afterwards as the persistence assert. Avoids unreliable swipe/confirm delete paths entirely.
- After driving any mutation through the UI, assert at the STORAGE layer, not just the DOM — the DOM can show optimistic/local state (live-reorder, uncommitted writes) while the database never persisted, so a DOM-only assertion passes on a broken app. First derive WHERE the app actually persists (read its load/persist code): a NATIVE SQLite file → pull BINARY-SAFE (`adb shell cat` mangles bytes LF->CRLF, so `adb shell run-as <pkg> base64 <db-path>` decoded locally, or `adb exec-out run-as <pkg> cat`; always pull `-wal`/`-shm` sidecars too or recent commits may be invisible); a sql.js/WebView localStorage base64 DB → read the storage key back over CDP, there is no file to pull. If neither is reachable from the harness, fall back to a behavioral membership assert (e.g. list visibility, since list queries filter deleted rows) and say so in the report.
- API 35+ redacts OTP-looking notification content (contiguous 4+ digits) for listeners lacking RECEIVE_SENSITIVE_NOTIFICATIONS: listener sees body "Sensitive notification content hidden". Use NBSP-grouped amounts in fixtures (real Revolut bodies group thousands with NBSP, so "4 500 Ft" is immune; only unusual ungrouped formats like "4500 Ft" trip the redactor). Decision: DROP unrecoverable redacted payloads, never persist junk amount-null rows — a redacted body never carries a usable merchant/amount, and persisting it would both show a "Sensitive notification content hidden" transaction to the user and pollute auto-tag learning. Guard in BOTH layers — the ingestion layer returns null before any dedup/auto-tag/dedup-window logic can observe it (TS IngestionService ingestNotification step 0 + RevolutNotificationService.toNotificationData early return) — and assert 0 rows + empty-state in the scenario. Flagging-only is wrong: a flagged-but-persisted redacted row is still a fake transaction the user would edit/delete. RECEIVE_SENSITIVE_NOTIFICATIONS is signature/role-level and cannot be held by a Play-store app, so requesting it is a dead end (and a policy risk) — do not pursue it.
- An attached AVD may be HEADLESS (`qemu-system-*-headless`): no emulator window exists. Judge liveness by `adb devices` + process list, not a visible window — when the user reports "emulator not up", say it is headless instead of restarting the AVD mid-run.
- PROGRESS VISIBILITY (user preference, deterministic suites): the runner must
  emit one `PROGRESS i/N — <scenario> — PASS/FAIL` line per completed scenario
  AND append the same line to `<out_dir>/PROGRESS` so `tail PROGRESS` / `ls |
  wc -l` shows X/N at a glance; write each scenario's DOM dump as it completes
  (never batch dumps to the end) so the out dir is a live progress ledger.
  Once a harness is proven stable, RUN the suite as a background TERMINAL
  process with `heartbeat=60` or `notify=['PROGRESS']` so the user receives
  live progress notifications; dispatch a subagent only while the harness may
  still need repair. The delegation live transcript
  (`<hermes>/cache/delegation/live/<deleg_id>/task-0.log`) is a tail-able
  progress view for any subagent — give the user the path.
- Keep a scratchpad at .maestro/SMOKE_SCRATCHPAD.md and dumps/report under .maestro/smoke_out/.

## Toolchain setup on a managed Mac (no admin/sudo)
- JDK: `brew install openjdk@21` (FORMULA, keg-only, no sudo). The Temurin CASK
  needs sudo -> blocked for non-admin. Gradle only needs JAVA_HOME.
- SDK: install into one ANDROID_HOME: `sdkmanager --sdk_root=$ANDROID_HOME
  platform-tools 'platforms;android-36' 'build-tools;36.0.0' emulator
  'system-images;android-35;google_apis;arm64-v8a' 'cmdline-tools;latest'`.
  Use the SDK-local avdmanager so it resolves images.
- Apple Silicon: arm64-v8a system images (native, fast).
- Capacitor build: `npm i && npm run build && npx cap sync android &&
  ./gradlew assembleDebug` (write android/local.properties sdk.dir). The npm
  `android:run` may hardcode Windows gradlew.bat -> use `./gradlew`.
- Installed package id = android `namespace`, which can differ from Capacitor
  `appId` (here `com.treasuryscribe.app` vs `com.vitobudget.tracker`).
- PIN CDP TO THE APP PID. Other apps' WebViews keep stale
  `webview_devtools_remote_<pid>` sockets on a busy AVD; resolving the FIRST socket
  silently attaches the whole oracle to the wrong app (proven: reads came from a leaked
  treasury-scribe WebView, scenarios even PASSED on it). Resolve
  `adb shell pidof <pkg>` and accept ONLY the socket with that exact PID; if pidof is
  empty, retry/fail — never fall back to "some" socket.
- cmd.exe (Windows host `subprocess(shell=True)`) + POSIX redirects: `adb shell am
  start ... >/dev/null 2>&1` SILENTLY no-ops the WHOLE command (cmd can't open
  /dev/null). Strip redirects from every adb string that may run under cmd; the
  wrapper captures output anyway. Same bug hid `pm clear`, so a frozen backgrounded
  WebView with a zombie devtools socket survived across runs.
- Right after pm clear/cold start the devtools socket is LISTED in /proc/net/unix
  BEFORE its HTTP endpoint answers — curl /json/list returns empty. live_ws needs a
  bounded retry loop (re-resolving the app PID each attempt), not a single shot.
- Windows git-bash: `python3` on PATH is often the WindowsApps stub; a shim exec'ing
  the native python must `cygpath -w` absolute args — native python cannot open
  `/c/...` paths that bash scripts pass.
- PRE-FIX NEGATIVE CONTROL (every on-device bugfix, not just scroll): when the bug is
  user-reported device behavior, also run the new scenarios against a PRE-FIX APK and
  report it honestly. It distinguishes 'fix ineffective' from 'the platform already
  masks the bug in some environments' (so the fix must not regress what native
  behavior provided) and catches fixes that make behavior WORSE. Also verify what is
  actually installed before trusting any verdict: unzip the APK and grep
  assets/public JS for the fix's code shape — a stale install invalidates every result.
- Scroll/viewport scenarios on Capacitor WebView: Chrome RESTORES window scroll on
  same-document traversals (history.back / navigate(-1)) when the document stays tall
  (warm DB + rows back before restoration = no loading clamp), so such a scenario can
  PASS on the pre-fix bundle — see the negative-control rule. PITFALL (passive-effect
  trap): a `useEffect` unmount cleanup that READS `window.scrollY` runs after the new
  route's shorter page has committed — the offset is ALREADY CLAMPED (docH −
  viewport), so the hook saves the clamped value and its restore then preempts the
  native one; mocked-scrollY unit tests cannot see this layout race.