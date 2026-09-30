#!/usr/bin/env bash
set -euo pipefail

: "${SDK_STAGE:?SDK_STAGE is required}"
: "${CRASHPAD_SRC:?CRASHPAD_SRC is required}"
: "${SDK_OS:?SDK_OS is required}"
: "${SDK_ARCH:?SDK_ARCH is required}"
: "${SDK_CONFIGURATION:?SDK_CONFIGURATION is required}"
: "${SDK_MINIMUM_SYSTEM_VERSION:?SDK_MINIMUM_SYSTEM_VERSION is required}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ ! -e "$SDK_STAGE" ]] || { echo "staging output must not exist: $SDK_STAGE" >&2; exit 1; }
read_config_value() {
  python3 - "$ROOT/$1" "$2" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1], encoding="utf-8"))[sys.argv[2]])
PY
}

SDK_VERSION="$(read_config_value config/sdk-version.json sdkVersion)"
CRASHPAD_REVISION="$(read_config_value config/source-lock.json crashpadRevision)"
EXPECTED_MINIMUM_SYSTEM_VERSION="$(python3 - "$ROOT/config/platform-matrix.json" "$SDK_OS" "$SDK_ARCH" "$SDK_CONFIGURATION" <<'PY'
import json
import sys
for target in json.load(open(sys.argv[1], encoding="utf-8"))["platforms"]:
    if target["os"] == sys.argv[2] and target["arch"] == sys.argv[3] and target["configuration"] == sys.argv[4]:
        print(target["minimumSystemVersion"])
        break
else:
    raise SystemExit("unsupported SDK target")
PY
)"
[[ "$SDK_MINIMUM_SYSTEM_VERSION" == "$EXPECTED_MINIMUM_SYSTEM_VERSION" ]] || {
  echo "SDK_MINIMUM_SYSTEM_VERSION does not match the platform matrix" >&2
  exit 1
}

mkdir -p "$SDK_STAGE/bin" "$SDK_STAGE/cmake" "$SDK_STAGE/licenses" "$SDK_STAGE/include/crashpad" "$SDK_STAGE/lib"
[[ -f "$CRASHPAD_SRC/LICENSE" ]] || { echo "Crashpad source LICENSE is missing" >&2; exit 1; }
cp "$CRASHPAD_SRC/LICENSE" "$SDK_STAGE/licenses/CRASHPAD-LICENSE"
for directory in client compat minidump snapshot util; do
  cp -R "$CRASHPAD_SRC/$directory" "$SDK_STAGE/include/crashpad/"
done
mini_chromium_dir="$CRASHPAD_SRC/third_party/mini_chromium/mini_chromium"
[[ -d "$mini_chromium_dir" ]] || { echo "Crashpad mini_chromium headers are missing: $mini_chromium_dir" >&2; exit 1; }
cp -R "$mini_chromium_dir" "$SDK_STAGE/include/mini_chromium"
case "$SDK_OS:$SDK_CONFIGURATION" in
  macos:release|windows:release) build_configuration="Release" ;;
  windows:debug) build_configuration="Debug" ;;
  *) echo "unsupported SDK platform/configuration: $SDK_OS/$SDK_CONFIGURATION" >&2; exit 2 ;;
esac
build_dir="$CRASHPAD_SRC/out/$build_configuration-$SDK_ARCH"
generated_dir="$build_dir/gen"
[[ -d "$generated_dir" ]] || { echo "Crashpad generated headers are missing: $generated_dir" >&2; exit 1; }
cp -R "$generated_dir" "$SDK_STAGE/include/"
if [[ "$SDK_OS" == "windows" ]]; then
  client_library="$(find "$build_dir" -type f -name 'client.lib' -print -quit)"
  database_library="$(find "$build_dir" -type f -name 'common.lib' -print -quit)"
else
  # GN prefixes static library names with "lib" on Apple platforms.
  client_library="$(find "$build_dir" -type f \( -name 'libclient.a' -o -name 'client.a' \) -print -quit)"
  database_library="$(find "$build_dir" -type f \( -name 'libcommon.a' -o -name 'common.a' \) -print -quit)"
fi
[[ -n "$client_library" ]] || {
  echo "Crashpad client library is missing under $build_dir" >&2
  exit 1
}
[[ -n "$database_library" ]] || {
  echo "Crashpad database library is missing under $build_dir" >&2
  exit 1
}
find "$build_dir" \( -name '*.a' -o -name '*.lib' \) -exec cp {} "$SDK_STAGE/lib/" \;
if [[ "$SDK_OS" == "windows" ]]; then
  handler_name="crashpad_handler.exe"
else
  handler_name="crashpad_handler"
fi
handler="$build_dir/$handler_name"
[[ -f "$handler" ]] || { echo "Crashpad handler is missing: $handler" >&2; exit 1; }
cp "$handler" "$SDK_STAGE/bin/$handler_name"

cat > "$SDK_STAGE/manifest.json" <<JSON
{"schemaVersion":3,"sdkVersion":"$SDK_VERSION","os":"$SDK_OS","arch":"$SDK_ARCH","configuration":"$SDK_CONFIGURATION","minimumSystemVersion":"$SDK_MINIMUM_SYSTEM_VERSION","crashpadRevision":"$CRASHPAD_REVISION","licenseMode":"bsd-compatible"}
JSON
cat > "$SDK_STAGE/cmake/CrashpadConfig.cmake" <<'CMAKE'
get_filename_component(PACKAGE_PREFIX_DIR "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
include("${CMAKE_CURRENT_LIST_DIR}/CrashpadTargets.cmake")
set(Crashpad_INCLUDE_DIR "${PACKAGE_PREFIX_DIR}/include")
if(WIN32)
  set(Crashpad_HANDLER_PATH "${PACKAGE_PREFIX_DIR}/bin/crashpad_handler.exe")
else()
  set(Crashpad_HANDLER_PATH "${PACKAGE_PREFIX_DIR}/bin/crashpad_handler")
endif()
CMAKE
cat > "$SDK_STAGE/cmake/CrashpadConfigVersion.cmake" <<CMAKE
set(PACKAGE_VERSION "$SDK_VERSION")
if(PACKAGE_FIND_VERSION VERSION_EQUAL PACKAGE_VERSION)
  set(PACKAGE_VERSION_COMPATIBLE TRUE)
  set(PACKAGE_VERSION_EXACT TRUE)
endif()
CMAKE
cat > "$SDK_STAGE/cmake/CrashpadTargets.cmake" <<'CMAKE'
get_filename_component(_crashpad_root "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
if(NOT TARGET Crashpad::Client)
  add_library(Crashpad::Client INTERFACE IMPORTED)
  if(WIN32)
    file(GLOB _crashpad_libs "${_crashpad_root}/lib/*.lib")
  else()
    file(GLOB _crashpad_libs "${_crashpad_root}/lib/*.a")
  endif()
  if(APPLE)
    set(_crashpad_system_libs "-lbsm")
  elseif(WIN32)
    set(_crashpad_system_libs Advapi32 Bcrypt Userenv Version Ws2_32)
  else()
    set(_crashpad_system_libs)
  endif()
  set_target_properties(Crashpad::Client PROPERTIES
    INTERFACE_INCLUDE_DIRECTORIES "${_crashpad_root}/include;${_crashpad_root}/include/crashpad;${_crashpad_root}/include/mini_chromium;${_crashpad_root}/include/gen"
    INTERFACE_LINK_LIBRARIES "${_crashpad_libs};${_crashpad_system_libs}")
endif()
CMAKE
