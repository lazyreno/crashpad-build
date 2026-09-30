#!/usr/bin/env python3
"""Reject SDKs whose client archive cannot enumerate existing crash reports."""

import argparse
from pathlib import Path


SYMBOL = b"InitializeWithoutCreating"


parser = argparse.ArgumentParser()
parser.add_argument("sdk_root", type=Path)
args = parser.parse_args()

libraries = [args.sdk_root / "lib" / name for name in ("client.lib", "client.a")]
client_library = next((library for library in libraries if library.is_file()), None)
if client_library is None:
    raise SystemExit(f"Crashpad client archive is missing under {args.sdk_root / 'lib'}")

if SYMBOL not in client_library.read_bytes():
    raise SystemExit(
        f"{client_library}: missing CrashReportDatabase::InitializeWithoutCreating"
    )

print(f"Crashpad client database API valid: {client_library}")
