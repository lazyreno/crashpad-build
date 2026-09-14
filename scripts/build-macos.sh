#!/usr/bin/env bash
set -euo pipefail
: "${SDK_ARCH:?SDK_ARCH is required}"
: "${CRASHPAD_SRC:?CRASHPAD_SRC is required}"
: "${SDK_STAGE:?SDK_STAGE is required}"
cd "$CRASHPAD_SRC"
out="$CRASHPAD_SRC/out/Release-$SDK_ARCH"
mkdir -p "$out"
if command -v gn >/dev/null 2>&1 && command -v autoninja >/dev/null 2>&1; then
  # Apple Clang on hosted macOS runners spells the C++23 mode c++2b.
  gn gen "$out" --args="target_os=\"mac\" target_cpu=\"$SDK_ARCH\" is_debug=false cflags_cc=[\"-std=c++2b\"]"
  autoninja -C "$out" crashpad_handler
else
  echo 'gn/autoninja unavailable; CI must provision depot_tools' >&2; exit 2
fi
mkdir -p "$SDK_STAGE/bin" "$SDK_STAGE/include" "$SDK_STAGE/lib"
cp "$out/crashpad_handler" "$SDK_STAGE/bin/"
cp -R "$CRASHPAD_SRC/third_party/mini_chromium/mini_chromium" "$SDK_STAGE/include/mini_chromium" 2>/dev/null || true
