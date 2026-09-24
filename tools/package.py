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
import re
import subprocess
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from convert import Converter, ROOT

YELLOW_REFERENCE = re.compile(r'"(yellow_src/[^"]+)"')


def merged_files(generated: Path) -> list[Path]:
    """Everything a build with both games needs beyond the Undertale package.

    The Yellow conversion is never regenerated here: it needs the pinned source
    fetched by tools/fetch_yellow.py, and a merged archive must not ship a
    half-converted game. A partial or failed Yellow conversion stops the build.
    """
    yellow = generated / "yellow"
    report_path = yellow / "conversion-report.json"
    if not report_path.is_file():
        raise ValueError(
            "Merged packaging needs a complete Yellow conversion first: "
            "python3 tools/fetch_yellow.py && python3 tools/yellow_convert.py --stage rooms"
        )
    report = json.loads(report_path.read_text())
    if report.get("stage") != "rooms":
        raise ValueError(f"Yellow conversion stopped at stage {report.get('stage')!r}; a merged build needs the rooms stage.")
    for section in ("scripts", "objects", "rooms"):
        errors = (report.get(section) or {}).get("compile_errors") or []
        if errors:
            raise ValueError(f"Yellow {section} conversion has {len(errors)} compile errors; refusing to package a merged build.")
    subprocess.run([sys.executable, str(ROOT / "tools/merge.py")], cwd=ROOT, check=True)
    # tools/merge.py writes two modules. v1.2.4 shipped only the manifest, so
    # every merged archive stopped on boot at require("generated.merged.items").
    # The native gate did not notice: LOVE's require also searches the process
    # cwd, and merge.py had just written the catalog there. The archive itself
    # has to carry it. Any later module written beside those two ships too.
    merged_dir = generated / "merged"
    required = ("manifest.lua", "items.lua")
    missing_modules = [name for name in required if not (merged_dir / name).is_file()]
    if missing_modules:
        raise ValueError(
            "Merged packaging is missing "
            + ", ".join(f"generated/merged/{name}" for name in missing_modules)
            + ". tools/merge.py must write the shared item catalog; without "
            "generated/merged/items.lua the archive stops on boot."
        )
    files = [merged_dir / name for name in required]
    files += sorted(path for path in merged_dir.glob("*.lua") if path.name not in required)
    files += sorted(path for path in yellow.rglob("*")
                    if path.is_file() and not any(part.startswith(".") for part in path.relative_to(ROOT).parts))
    # The converted records open their assets by archive-relative path inside
    # the pinned checkout (sprite frames, sounds, font atlases, tileset pages).
    # A merged archive that shipped the modules without those files would draw
    # nothing and play no sound, so the referenced set is derived from the
    # records themselves - never copied wholesale from the ~580 MB checkout -
    # and a missing file stops the build instead of failing at runtime.
    referenced = set()
    for module in yellow.rglob("*.lua"):
        referenced.update(YELLOW_REFERENCE.findall(module.read_text(encoding="utf-8")))
    missing = sorted(name for name in referenced if not (ROOT / name).is_file())
    if missing:
        raise ValueError(
            f"{len(missing)} pinned Yellow files referenced by the conversion are absent "
            f"(run tools/fetch_yellow.py); first: {missing[0]}"
        )
    files += [ROOT / name for name in sorted(referenced)]
    print(f"Merged archive carries {len(referenced)} referenced pinned Yellow asset files.")
    return files


def package(output: Path, regenerate=True, merged=False):
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
    # Recovered path geometry is baked into the generated manifest; the file it came
    # from ships alongside it so anyone can audit the provenance offline.
    if (ROOT / "port/path_data.json").is_file():
        files.append(ROOT / "port/path_data.json")
    if (ROOT / "port/recovered_registry.json").is_file():
        files.append(ROOT / "port/recovered_registry.json")
    recovered_rooms = ROOT / "port/recovered_rooms"
    if recovered_rooms.is_dir():
        files += sorted(recovered_rooms.iterdir())
    files += [generated / name for name in report["generated_files"]]
    if merged:
        files += merged_files(generated)
    for directory, extension in [("sprites/images", ".png"), ("background/images", ".png"), ("fonts", ".png")]:
        files += sorted((ROOT / directory).glob("*" + extension))
    files += sorted(p for p in (ROOT / "sound/audio").iterdir() if p.suffix.lower() in (".wav", ".ogg", ".mp3"))
    for name in ["README.md", "docs/PORTING.md", "docs/ANDROID.md", "docs/CONTROLS.md", "docs/VALIDATION.md",
                 "docs/PATHS.md"]:
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
            names = set(archive.namelist())
            assert "main.lua" in names and "conf.lua" in names
            if merged:
                required = {"generated/merged/manifest.lua", "generated/merged/items.lua"}
                absent = sorted(required - names)
                if absent:
                    raise ValueError(
                        "Merged archive omitted " + ", ".join(absent)
                        + ". The shared item catalog must be inside the .love; "
                        "a copy beside the process is not a substitute."
                    )
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
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--no-convert", action="store_true", help="Reuse an already validated generated/ tree")
    parser.add_argument("--merged", action="store_true",
                        help="Package both games: Undertale plus a complete Undertale Yellow conversion and the travel bridge")
    args = parser.parse_args()
    default = "undertale-merged-love-experimental.love" if args.merged else "undertale-love-experimental.love"
    output = (args.output or (ROOT / "artifacts" / default)).resolve()
    try:
        package(output, regenerate=not args.no_convert, merged=args.merged)
    except (ValueError, OSError) as exc:
        print(f"Packaging failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
