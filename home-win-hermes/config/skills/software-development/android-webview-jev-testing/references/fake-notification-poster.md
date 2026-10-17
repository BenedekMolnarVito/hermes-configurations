# Fake notification poster APK (smoke-test the real NLS path)

Minimal Gradle project (copy gradlew + gradle/ wrapper + local.properties from the app's android/ dir). AGP must match the app (8.13.0 here). Build: `./gradlew assembleDebug`; install with `adb -s emulator-5554 install -r -g`.

settings.gradle: pluginManagement/dependencyResolutionManagement repos google()+mavenCentral(); include ':app'.
build.gradle: `plugins { id 'com.android.application' version '8.13.0' apply false }`
gradle.properties: `android.useAndroidX=true`
app/build.gradle: namespace + applicationId = the allow-listed package (com.revolut.revolut), compileSdk/targetSdk 36, minSdk 24.
Manifest: POST_NOTIFICATIONS permission; one exported Activity `.Post` with `@android:style/Theme.NoDisplay`.

Post.java onCreate: decode extras `t64`/`b64` (Base64.DEFAULT, UTF-8); create channel "tx" IMPORTANCE_HIGH; `Notification.Builder(this,"tx").setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle(title).setContentText(body).setStyle(new Notification.BigTextStyle().bigText(body))`; notify with a unique id; finish().
setContentText is required: the listener reads EXTRA_TEXT.

Drive: `adb -s emulator-5554 shell am start -n com.revolut.revolut/.Post --es t64 <b64 title> --es b64 <b64 body>`; wait ~2.5s per post.

## Deterministic version (for edge-case suites)
The sleep-and-hope poster above is fine for a single post. For a replayable suite, use a richer fixture (the Treasury Scribe in-repo one lives at .maestro/smoke/fixtures/poster). It should have:
- Extras for `id` (fixed, enables update tests), `group`, `summary` (setGroupSummary), and `action` = post/cancel/cancelAll. Build a second copy with another applicationId (Gradle `-PposterAppId=`) for the negative "other package" case; you can't spoof the package from inside the same APK.
- A confirmation instead of a fixed sleep: echo a caller `nonce`, poll getActiveNotifications until the requested state is visible, then log one `TAG: {json}` line containing id/flags/isSummary/postTime. Read it back with `logcat -d -v raw -s TAG:I`.
- A translucent theme (not NoDisplay), so the Activity can outlive the async confirmation. Handle the intent in onCreate AND onNewIntent, because repeated `am start` calls reach the live instance.
- Empty strings sent as a sentinel (`~EMPTY~`), because `am start --es k ""` drops the value.
- NBSP-grouped amounts in payloads. On API 35+, contiguous 4+ digits get OTP-redacted.
- A rule that autogroup flags come from the OS (post 4+ ungrouped notifications), never forged. Verify them via `dumpsys notification --noredact` (`tag=ranker_group`).
