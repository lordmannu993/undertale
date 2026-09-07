#!/usr/bin/env python3
"""Build a reproducible .love ZIP with main.lua at the archive root.

This produces an EXPERIMENTAL LÖVE port, not a completed Android APK. Never
package the entire repository: that leaks .git, local saves and build tooling.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from convert import Converter, ROOT


def package(output: Path, regenerate=True):
    generated = ROOT / "generated"
    if regenerate:
        report = Converter(ROOT, generated).run()
    else:
        report = json.loads((generated / "conversion-report.json").read_text())
    if report.get("compile_errors") or report.get("missing_asset_files"):
        raise ValueError("Cannot package failed translation or missing listed asset files. Inspect conversion-report.json.")
    if output.suffix != ".love" or output.resolve().is_relative_to(ROOT / ".git"):
        raise ValueError("Output must end in .love and must not be inside .git")
    files = [ROOT / "main.lua", ROOT / "conf.lua"]
    files += sorted((ROOT / "port").glob("*.lua"))
    files += [ROOT / "port/resource_overrides.json"]
    files += [generated / name for name in report["generated_files"]]
    for directory, extension in [("sprites/images", ".png"), ("background/images", ".png"), ("fonts", ".png")]:
        files += sorted((ROOT / directory).glob("*" + extension))
    files += sorted(p for p in (ROOT / "sound/audio").iterdir() if p.suffix.lower() in (".wav", ".ogg", ".mp3"))
    for name in ["README.md", "docs/PORTING.md", "docs/ANDROID.md", "docs/CONTROLS.md", "docs/VALIDATION.md"]:
        p = ROOT / name
        if p.exists():
            files.append(p)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(".love.tmp")
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(set(files)):
                if not path.resolve().is_relative_to(ROOT.resolve()) or path.is_symlink():
                    raise ValueError(f"Unsafe package path: {path}")
                relative = path.relative_to(ROOT).as_posix()
                if any(part.startswith(".") for part in Path(relative).parts):
                    raise ValueError(f"Hidden file cannot be packaged: {relative}")
                info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        with zipfile.ZipFile(temp) as archive:
            assert "main.lua" in archive.namelist() and "conf.lua" in archive.namelist()
            broken = archive.testzip()
            if broken:
                raise ValueError(f"Archive CRC failed: {broken}")
        temp.replace(output)
    finally:
        if temp.exists():
            temp.unlink()
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".love.sha256").write_text(f"{digest}  {output.name}\n")
    output.with_suffix(".conversion-report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(f"Built {output} ({output.stat().st_size / 1024**2:.1f} MiB)")
    print(f"SHA-256: {digest}")
    print(f"EXPERIMENTAL: {len(report['missing_paths'])} missing paths and {len(report['unresolved_numeric_references'])} unresolved static asset references.")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/undertale-love-experimental.love")
    parser.add_argument("--no-convert", action="store_true", help="Reuse an already validated generated/ tree")
    args = parser.parse_args()
    try:
        package(args.output.resolve(), regenerate=not args.no_convert)
    except (ValueError, OSError) as exc:
        print(f"Packaging failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
