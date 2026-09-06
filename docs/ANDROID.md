# Android: run the archive or build a development APK

## Current status

**An experimental `.love` archive can be built now. An APK has not been compiled
or device-tested in this workspace.** Missing source resources and compatibility
work still block full-game playability. Packaging does not fix those issues.

## Easiest way to try it — official LÖVE Android runner

1. On your computer, run `python3 tools/package.py`.
2. Install the official **LÖVE 11.5 Android runner**, available from the
   [LÖVE releases](https://github.com/love2d/love/releases/tag/11.5).
3. Transfer `artifacts/undertale-love-experimental.love` to your phone.
4. Open the `.love` file with LÖVE from your file manager (grant the file access
   requested by Android). File-manager “Open with” support varies; another file
   manager may be needed.
5. Touch controls appear automatically on Android. Back opens PAUSE. Try the
   control tester before starting a battle.

The `.love` archive already contains generated Lua and the supplied assets.
Python, GameMaker, a desktop keyboard and a compiler are not needed on the phone.
Simply renaming `.love` or `.gmx` to `.apk` does **not** produce an APK.

## Standalone development APK

The build script uses upstream **love-android 11.5a**, pinned to commit
`55feb38fa144f4734c26742389f279fb07d955c0`. Its Gradle files specify:

- JDK **17**
- Android SDK platform **34**
- Android build-tools **34.0.0**
- Android NDK **25.2.9519653**
- Git (including recursive submodule access)
- Gradle 8.1, provided by the upstream wrapper

These versions are intentionally taken from that pinned runner, not from its
moving default-branch README. Use Android Studio's SDK Manager or `sdkmanager` to
install the components, and accept the SDK licenses yourself.

```sh
# Example after installing Android SDK command-line tools and selecting JDK 17:
export ANDROID_HOME="$HOME/Android/Sdk"
sdkmanager 'platforms;android-34' 'build-tools;34.0.0' 'ndk;25.2.9519653'

python3 tools/build_android.py --allow-experimental
```

Windows: use `python`, configure `ANDROID_HOME`/`JAVA_HOME` in your environment,
and run from a shell that can execute Git and the Gradle batch wrapper.

The script:

1. Checks the JDK and SDK/NDK prerequisites before attempting a build.
2. Regenerates and packages the `.love` archive.
3. Fetches a **separate dependency checkout** under `.android/love-android` and
   checks its pinned commit. It never checks out a different game-project branch.
4. Embeds the archive at `app/src/embed/assets/game.love`.
5. Sets package ID `org.undertale.loveport.experimental`, a clearly experimental
   app name, and `sensorLandscape` orientation (both landscape rotations).
6. Runs `:app:assembleEmbedNoRecordDebug` using the upstream Gradle wrapper.
7. Copies the resulting, development-signed APK to
   `artifacts/undertale-love-experimental-debug.apk` **only if the build succeeds**.

No microphone flavor, private signing credentials, GitHub credentials, or
commercial GameMaker export license are required. Gradle uses its normal local
debug key; it must not be used for a public production release. Do not commit a
keystore or SDK directory. A fresh clone does require network access and enough
space/time to compile the native runner.

With USB debugging enabled and `adb` installed:

```sh
adb install -r artifacts/undertale-love-experimental-debug.apk
adb logcat
```

An install/signature conflict with another package should be investigated before
uninstalling: uninstalling removes that app's saves. This package ID is distinct
from the official game and official LÖVE runner.

## GitHub Actions alternative

After this branch's changes are pushed to your repository, manually run
**Experimental Android APK (manual)** and acknowledge the incomplete-port and
asset-rights notice. It installs the pinned toolchain, runs tests, and attempts
the same debug build. Download the APK artifact only if the job succeeds.

The workflow is supplied but has **not been run or verified here**. Automatic
push/PR test jobs upload test results only, not the game or its assets.

## Not a Play Store release configuration

The pinned runner is useful for development, not a claim of compliance with
2026 Play Store requirements. Before distribution, independently validate/update
its target SDK, native dependencies, ABI coverage, **16 KB memory-page support**,
permissions, icons, versioning, privacy requirements and release signing. Native
libraries built by the older pinned NDK may not work on all newer 16 KB-page
Android devices. A successful debug build is not a substitute for that work.

Do not publish this incomplete build as a finished port. This repository's
provenance does not grant rights to distribute the original game's assets.

## Saves and diagnostics

LÖVE identity: `undertale-love-port`, with `t.externalstorage = false`. Saves use
LÖVE's app-private save location and do not modify desktop Undertale saves.
GameMaker text/INI save filenames are retained inside that sandbox. PAUSE and app
suspension flush writes; quick resume does not fast-forward the game.

A compatibility stop writes `last-port-error.txt` to the LÖVE save directory and
prints the object/event/room to the log. Attach that diagnostic and the
`generated/conversion-report.json` from your build when reporting a problem.
