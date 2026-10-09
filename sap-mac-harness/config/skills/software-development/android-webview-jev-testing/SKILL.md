---
name: android-webview-jev-testing
description: "Use to DOM-test a Capacitor Android WebView with Jev."
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
3. CDP `/json` may 404 (Host-header protection) but `/json/list` and
   `/json/version` work once forwarded to the right socket.
4. Debug APK already exposes CDP. A release build needs
   `WebView.setWebContentsDebuggingEnabled(true)`.
5. App may chain STARTUP PERMISSION REDIRECTS (notification-listener access,
   battery-optimization exemption) that steal foreground. Grant via adb
   (`pm grant`, `cmd notification allow_listener`) or press Back to dismiss.
6. execute_code kernel does NOT inherit the shell env. Load the key with
   `zsh -c 'source ~/.zshrc; printf "%s\0" "$TYPESAFE_API_KEY"'` and split on
   NUL (interactive `-i` injects stray chars; `${#VAR}` gives the true length).

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

## Behavioral smoke-test workflow (Treasury Scribe, proven)
- The installed APK goes STALE: before testing a branch, check `find src -newer <apk>` and REBUILD (npm run build; npx cap sync android; cd android && ./gradlew assembleDebug) + `adb install -r -g` the fresh APK. The npm `android:run` hardcodes Windows gradlew.bat — use `./gradlew`.
- Maestro is NOT the DOM tool here: a Capacitor WebView's DOM is absent from the a11y tree, so Maestro assertions see nothing. Use Maestro only to boot/launch; do all behavioral assertions via CDP DOM + Jev (jev_dom_runner.py).
- Jev loop verdicts are noisy on multi-step nav: trust the DUMPED DOM over the Jev score. A UNCERTAIN/FAIL often just means the loop didn't reach the screen; a false PASS can happen when a lookalike control (e.g. a Default/Exception toggle in the Add modal) is mistaken for the target screen (Edit). Always confirm `url` + testids in the dumped DOM.
- Many features are DATA-GATED (tag cloud show-more needs >8 tags, edit/back needs a txn to edit). Seed via the app's OWN Add-Transaction modal over CDP: set React-controlled inputs with the native value setter + dispatched 'input' event (NOT el.value=), find fields by placeholder/data-testid. Submit auto-commits trailing tag text.
- NOT emulator-drivable, cover by unit tests instead: (1) file export/import round-trips (Capacitor Share/Filesystem write + native file picker); (2) notification-ingestion logic — the listener fires ONLY for its allow-listed source package (e.g. com.revolut.revolut), which adb cannot spoof. Run the targeted vitest suites as supporting evidence; never fabricate on-device results for these.
- adb `input swipe` does NOT reliably trigger React swipe-to-delete handlers (they need a held drag). Prefer an in-DOM control or the repo/hook path over a synthetic swipe.
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