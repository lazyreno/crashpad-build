#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
from pathlib import Path


def run(*command):
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def find_dumpbin():
    program_files = os.environ.get("ProgramFiles(x86)")
    if not program_files:
        raise SystemExit("ProgramFiles(x86) is not set; cannot locate dumpbin")
    vswhere = Path(program_files) / "Microsoft Visual Studio/Installer/vswhere.exe"
    installation = run(
        str(vswhere), "-latest", "-products", "*", "-requires",
        "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"
    ).strip()
    candidates = list((Path(installation) / "VC/Tools/MSVC").glob("*/bin/Hostx64/x64/dumpbin.exe"))
    if not candidates:
        raise SystemExit("dumpbin.exe was not found in the Visual Studio installation")
    return candidates[0]


parser = argparse.ArgumentParser()
parser.add_argument("--sdk-root", required=True, type=Path)
parser.add_argument("--minimum-system-version", required=True)
args = parser.parse_args()

handler = args.sdk_root / "bin/crashpad_handler.exe"
headers = run(str(find_dumpbin()), "/headers", str(handler))
match = re.search(r"^\s*(\d+)\.(\d+)\s+subsystem version$", headers, re.IGNORECASE | re.MULTILINE)
if not match:
    raise SystemExit(f"Crashpad handler PE subsystem version is missing: {handler}")
actual = tuple(map(int, match.groups()))
expected = tuple(map(int, args.minimum_system_version.split(".")))
if actual > expected:
    raise SystemExit(f"{handler}: PE subsystem {match.group(0).strip()} exceeds {args.minimum_system_version}")
print(f"Windows SDK subsystem valid: {args.minimum_system_version}")
