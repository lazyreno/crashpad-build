#!/usr/bin/env python3
"""Reject SDKs whose Crashpad database archive cannot enumerate existing reports."""

import argparse
from pathlib import Path


SYMBOL = b"InitializeWithoutCreating"


parser = argparse.ArgumentParser()
parser.add_argument("sdk_root", type=Path)
args = parser.parse_args()

libraries = [
    args.sdk_root / "lib" / name
    for name in ("common.lib", "libcommon.a", "common.a")
]
database_library = next((library for library in libraries if library.is_file()), None)
if database_library is None:
    raise SystemExit(f"Crashpad database archive is missing under {args.sdk_root / 'lib'}")

if SYMBOL not in database_library.read_bytes():
    raise SystemExit(
        f"{database_library}: missing CrashReportDatabase::InitializeWithoutCreating"
    )

print(f"Crashpad database API valid: {database_library}")
