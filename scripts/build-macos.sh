#!/usr/bin/env bash
set -euo pipefail
: "${SDK_ARCH:?SDK_ARCH is required}"
: "${CRASHPAD_SRC:?CRASHPAD_SRC is required}"
: "${SDK_MINIMUM_SYSTEM_VERSION:?SDK_MINIMUM_SYSTEM_VERSION is required}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
patch_file="$ROOT/patches/crashpad-macos-11-iokit-default-port.patch"
git -C "$CRASHPAD_SRC" apply --check "$patch_file"
git -C "$CRASHPAD_SRC" apply "$patch_file"
cd "$CRASHPAD_SRC"
out="$CRASHPAD_SRC/out/Release-$SDK_ARCH"
mkdir -p "$out"
if command -v gn >/dev/null 2>&1 && command -v autoninja >/dev/null 2>&1; then
  # Apple Clang on hosted macOS runners spells the C++23 mode c++2b.
  while IFS= read -r file; do
    sed -i '' 's/-std=c++23/-std=c++2b/g' "$file"
  done < <(rg -l -- '-std=c\+\+23' "$CRASHPAD_SRC" "$RUNNER_TEMP/buildtools" 2>/dev/null || true)
  gn gen "$out" --args="target_os=\"mac\" target_cpu=\"$SDK_ARCH\" is_debug=false mac_deployment_target=\"$SDK_MINIMUM_SYSTEM_VERSION\""
  find "$out" -type f -name '*.ninja' -exec sed -i '' 's/-std=c++23/-std=c++2b/g' {} +
  autoninja -C "$out" crashpad_handler client
  if [[ "${CRASHPAD_RUN_UPSTREAM_TESTS:-false}" == "true" ]]; then
    test_targets=(
      crashpad_client_test
      crashpad_handler_test
      crashpad_minidump_test
      crashpad_snapshot_test
      crashpad_test_test
      crashpad_util_test
    )
    autoninja -C "$out" "${test_targets[@]}"
    test_args=(--gtest_filter=-ExcClientVariants.UniversalExceptionRaise)
    for test_target in "${test_targets[@]}"; do
      CRASHPAD_TEST_DATA_ROOT="$CRASHPAD_SRC" "$out/$test_target" "${test_args[@]}"
    done
  fi
else
  echo 'gn/autoninja unavailable; CI must provision depot_tools' >&2; exit 2
fi
