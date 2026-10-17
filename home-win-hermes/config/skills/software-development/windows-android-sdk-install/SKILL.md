---
name: windows-android-sdk-install
description: "Use when Windows Android builds or USB installs fail."
---

# Windows Android SDK and device installation

- Compare Gradle's reported SDK path with Android Studio's SDK Location before accepting licenses or installing packages. A path ending in cmdline-tools/latest/bin is not an SDK root.
- Inspect android/local.properties and ANDROID_HOME/ANDROID_SDK_ROOT. Verify platforms/android-<compileSdk>/android.jar, required build-tools, licenses, and platform-tools/adb.exe under the intended root.
- Reproduce with gradlew.bat installDebug --dry-run --console=plain before fixing. Prefer Git-ignored android/local.properties with sdk.dir=C:/.../Android/Sdk for a checkout-specific fix; never commit machine paths. Keep process SDK variables consistent. ANDROID_SDK_ROOT is deprecated; remove it or match ANDROID_HOME. Persistent environment changes require new terminal/IDE sessions.
- From PowerShell 5.1, use cmd /c "npm run build && npx cap sync android && cd android && gradlew.bat installDebug" for fail-fast chaining. macOS uses ./gradlew; label both dialects when documenting.
- Confirm adb devices -l and the target model. INSTALL_FAILED_USER_RESTRICTED on Xiaomi/POCO can mean Install via USB is disabled or a device prompt was denied. Ask the user to unlock the phone, enable that setting, and approve installation; do not bypass restrictions.
- After approval, retry adb -s <serial> install -r <apk>. Do not uninstall or clear data. Read the actual application ID/activity before launching with am start -W and verify the process exists. Launch success is not functional smoke-test evidence.
- Hermes's terminal PATH puts its bundled Node (AppData/Local/hermes/tools/node-*) before the user's Node (e.g. scoop). Native modules like better-sqlite3 then fail with NODE_MODULE_VERSION mismatch. Check `which -a node` first and prepend the user's Node dir to PATH; never `npm rebuild` under Hermes's Node: node-gyp deletes the working .node before a failing compile.
- In this Git Bash, run `cmd.exe /d /c "..."` (single slash); `//c` silently runs nothing.
- Keep build logs in the declared Hermes scratch directory; on Windows inspect the resolved TMPDIR because it may unexpectedly point to system Temp. Report actual build/install outcomes separately, and run relevant project gates.
