#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("root", type=Path)
parser.add_argument("--os", required=True, choices=("macos", "windows"))
parser.add_argument("--arch", required=True, choices=("arm64", "x64"))
parser.add_argument("--configuration", required=True, choices=("release", "debug"))
parser.add_argument("--minimum-system-version", required=True)
args = parser.parse_args()

required = ["bin", "include", "lib", "cmake", "licenses", "manifest.json"]
missing = [item for item in required if not (args.root / item).exists()]
handler = "crashpad_handler.exe" if args.os == "windows" else "crashpad_handler"
if not (args.root / "bin" / handler).is_file():
    missing.append(f"bin/{handler}")
if missing:
    print("missing: " + ", ".join(missing), file=sys.stderr)
    raise SystemExit(1)

manifest = json.loads((args.root / "manifest.json").read_text(encoding="utf-8"))
source_lock = json.loads(
    (Path(__file__).resolve().parents[1] / "config/source-lock.json").read_text(encoding="utf-8")
)
if manifest.get("schemaVersion") != 3:
    raise SystemExit("manifest schemaVersion must be 3")
if manifest.get("os") != args.os or manifest.get("arch") != args.arch:
    raise SystemExit("manifest OS or architecture mismatch")
if manifest.get("configuration") != args.configuration:
    raise SystemExit("manifest configuration mismatch")
if manifest.get("minimumSystemVersion") != args.minimum_system_version:
    raise SystemExit("manifest minimumSystemVersion mismatch")
if manifest.get("crashpadRevision") != source_lock["crashpadRevision"]:
    raise SystemExit("manifest crashpadRevision mismatch")
print(f"SDK layout valid: {args.os}-{args.arch}-{args.configuration}")
