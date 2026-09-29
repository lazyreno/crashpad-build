#!/usr/bin/env python3
import argparse
import re
import subprocess
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--sdk-root", required=True, type=Path)
parser.add_argument("--minimum-system-version", required=True)
args = parser.parse_args()

handler = args.sdk_root / "bin/crashpad_handler"
if not handler.is_file():
    raise SystemExit(f"Crashpad handler is missing: {handler}")
output = subprocess.run(
    ["xcrun", "vtool", "-show-build", str(handler)], check=True, capture_output=True, text=True
).stdout
match = re.search(r"minos\s+(\d+(?:\.\d+)*)", output)
if not match:
    raise SystemExit(f"Crashpad handler has no macOS minos value: {handler}")
actual = tuple(map(int, match.group(1).split(".")))
expected = tuple(map(int, args.minimum_system_version.split(".")))
if actual > expected:
    raise SystemExit(f"{handler}: minos {match.group(1)} exceeds {args.minimum_system_version}")
print(f"macOS SDK minos valid: {args.minimum_system_version}")
