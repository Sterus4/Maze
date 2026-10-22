"""Build a debug APK using the project-local Godot tools and an existing SDK/JDK."""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(arguments, environment):
    result = subprocess.run([str(arg) for arg in arguments], env=environment,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            encoding="utf-8", errors="replace")
    print(result.stdout, flush=True)
    if result.returncode or "SCRIPT ERROR:" in result.stdout or "Parse Error:" in result.stdout:
        raise RuntimeError(f"Build step failed: {arguments[0]} (code {result.returncode})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--android-sdk", type=Path, default=Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk")
    parser.add_argument("--java-sdk", type=Path)
    parser.add_argument("--skip-data-export", action="store_true", help="preserve a previously exported custom maze catalog")
    args = parser.parse_args()
    if not (args.android_sdk / "platform-tools" / "adb.exe").exists():
        parser.error("Android SDK not found. Pass --android-sdk.")
    java = args.java_sdk
    if java is None:
        result = subprocess.run(["java", "-XshowSettings:properties", "-version"], capture_output=True, text=True)
        match = re.search(r"java.home\s*=\s*([^\r\n]+)", result.stdout + result.stderr)
        if match:
            java = Path(match.group(1).strip())
    if java is None or not (java / "bin" / "keytool.exe").exists():
        parser.error("JDK 17+ not found. Pass --java-sdk.")
    folder = ROOT / ".tools" / "godot"
    engine = folder / "Godot_v4.7.2-stable_win64_console.exe"
    if not engine.exists():
        parser.error("Run python scripts/fetch_godot.py first.")
    environment = dict(os.environ, JAVA_HOME=str(java), PYTHONIOENCODING="utf-8")
    # Use separate settings inside the ignored tools folder.
    (folder / "_sc_").touch()
    if not args.skip_data_export:
        run([sys.executable, ROOT / "scripts" / "export_android_mazes.py"], environment)
    project = ROOT / "android-game"
    run([engine, "--headless", "--path", project, "--editor", "--import", "--quit"], environment)
    settings_path = folder / "editor_data" / "editor_settings-4.7.tres"
    settings = settings_path.read_text(encoding="utf-8")
    for key, value in (("java_sdk_path", java), ("android_sdk_path", args.android_sdk)):
        line = f'export/android/{key} = "{value.as_posix()}"'
        settings = re.sub(rf"(?m)^export/android/{key} = .*?$", lambda _: line, settings)
    settings_path.write_text(settings, encoding="utf-8")
    output = ROOT / "build" / "Maze-Rooms-debug.apk"
    output.parent.mkdir(exist_ok=True)
    run([engine, "--headless", "--path", project, "--script", "res://tests/test_state.gd"], environment)
    run([engine, "--headless", "--path", project, "--export-debug", "Android", output], environment)
    if not output.exists():
        raise RuntimeError("APK was not produced.")
    print(f"APK: {output} ({output.stat().st_size / 1024 / 1024:.1f} MiB)")


if __name__ == "__main__":
    main()
