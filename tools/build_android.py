#!/usr/bin/env python3
"""Build a fused, debug-signed APK using a pinned upstream love-android runner.

This is a DEVICE-TEST build path, not Play Store release tooling. The port has
known source blockers. You must explicitly pass --allow-experimental.
Prerequisites: JDK 17, Git, Android platform/build-tools 34, NDK 25.2.9519653.
No credentials/signing secrets are requested or stored by this script.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from convert import ROOT
from package import package

RUNNER_URL = "https://github.com/love2d/love-android.git"
RUNNER_COMMIT = "55feb38fa144f4734c26742389f279fb07d955c0"  # upstream 11.5a
NDK = "25.2.9519653"


def run(*command, cwd=None, env=None):
    subprocess.run(command, cwd=cwd, env=env, check=True)


def preflight():
    java = shutil.which("java")
    if not java:
        raise RuntimeError("JDK 17 is not installed. Install it before building an APK; .love packaging does not need Java.")
    result = subprocess.run([java, "-version"], capture_output=True, text=True, check=True)
    if not re.search(r'version "17(?:\.|\")', result.stdout + result.stderr):
        raise RuntimeError("This pinned runner requires JDK 17. Select JDK 17 using JAVA_HOME/PATH.")
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not sdk:
        raise RuntimeError("Set ANDROID_HOME to your installed Android SDK (see docs/ANDROID.md).")
    sdk = Path(sdk).expanduser().resolve()
    for relative in ["platforms/android-34/android.jar", "build-tools/34.0.0", f"ndk/{NDK}/source.properties"]:
        if not (sdk / relative).exists():
            raise RuntimeError(f"Missing Android SDK component: {relative}. Install it with SDK Manager.")
    if not shutil.which("git"):
        raise RuntimeError("Git is needed to fetch the upstream LÖVE runner and its submodules.")
    return sdk


def configure_runner(runner):
    # This is an EXTERNAL DEPENDENCY checkout. Never change the game's branch.
    if runner == ROOT or runner.is_relative_to(ROOT / ".git") or ROOT.is_relative_to(runner):
        raise RuntimeError("Runner must be a separate dependency directory, never this repository or its parent.")
    if not runner.exists():
        runner.parent.mkdir(parents=True, exist_ok=True)
        run("git", "clone", "--no-checkout", RUNNER_URL, str(runner))
        run("git", "checkout", "--detach", RUNNER_COMMIT, cwd=runner)
    if not (runner / ".git").exists():
        raise RuntimeError("Existing runner directory is not a Git checkout. Choose a new --runner path.")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=runner, text=True).strip()
    if head != RUNNER_COMMIT:
        raise RuntimeError("Existing runner is not the pinned 11.5a commit. Use a fresh --runner directory; it will not be overwritten.")
    run("git", "submodule", "update", "--init", "--recursive", cwd=runner)
    properties = runner / "gradle.properties"
    text = properties.read_text()
    settings = {"app.name": "UNDERTALE LOVE (Experimental)", "app.application_id": "org.undertale.loveport.experimental",
                "app.orientation": "sensorLandscape", "app.version_code": "1", "app.version_name": "0.1-experimental"}
    lines = [line for line in text.splitlines() if not line.startswith("app.")]
    lines += [f"{key}={value}" for key, value in settings.items()]
    properties.write_text("\n".join(lines) + "\n")
    return runner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", type=Path, default=ROOT / ".android/love-android")
    parser.add_argument("--allow-experimental", action="store_true", help="Acknowledge that missing source resources prevent a complete game")
    args = parser.parse_args()
    if not args.allow_experimental:
        parser.error("This is not a finished full-game port. Read docs/PORTING.md, then pass --allow-experimental for a development APK.")
    try:
        sdk = preflight()
        archive = package(ROOT / "artifacts/undertale-love-experimental.love")
        runner = configure_runner(args.runner.expanduser().resolve())
        assets = runner / "app/src/embed/assets"
        assets.mkdir(parents=True, exist_ok=True)
        # main.lua inside game.love is at ZIP root, as required by love-android.
        shutil.copyfile(archive, assets / "game.love")
        env = os.environ.copy()
        env["ANDROID_HOME"] = str(sdk)
        env["JAVA_TOOL_OPTIONS"] = env.get("JAVA_TOOL_OPTIONS", "") + " -XX:ActiveProcessorCount=2"
        wrapper = "gradlew.bat" if os.name == "nt" else "./gradlew"
        run(wrapper, "--no-daemon", "--max-workers=2", ":app:assembleEmbedNoRecordDebug", cwd=runner, env=env)
        apks = list((runner / "app/build/outputs/apk/embedNoRecord/debug").glob("*.apk"))
        if len(apks) != 1:
            raise RuntimeError("Expected one embedNoRecord debug APK; inspect the upstream Gradle output.")
        destination = ROOT / "artifacts/undertale-love-experimental-debug.apk"
        shutil.copyfile(apks[0], destination)
        print(f"Built debug APK: {destination}")
        print("Development signing only. Not Play Store-ready or a full-game compatibility certification.")
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Android build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
