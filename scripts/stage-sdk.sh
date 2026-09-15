#!/usr/bin/env bash
set -euo pipefail
: "${SDK_STAGE:?}"; : "${SDK_VERSION:?}"; : "${PLATFORM:?}"; : "${SDK_ARCH:?}"
mkdir -p "$SDK_STAGE/cmake" "$SDK_STAGE/licenses"
mkdir -p "$SDK_STAGE/include/crashpad" "$SDK_STAGE/lib"
[[ -f "$CRASHPAD_SRC/LICENSE" ]] || { echo "Crashpad source LICENSE is missing" >&2; exit 1; }
cp "$CRASHPAD_SRC/LICENSE" "$SDK_STAGE/licenses/CRASHPAD-LICENSE"
if [[ -n "${CRASHPAD_SRC:-}" ]]; then
  cp -R "$CRASHPAD_SRC/client" "$SDK_STAGE/include/crashpad/"
  cp -R "$CRASHPAD_SRC/compat" "$SDK_STAGE/include/crashpad/"
  cp -R "$CRASHPAD_SRC/minidump" "$SDK_STAGE/include/crashpad/"
  cp -R "$CRASHPAD_SRC/snapshot" "$SDK_STAGE/include/crashpad/"
  cp -R "$CRASHPAD_SRC/util" "$SDK_STAGE/include/crashpad/"
  generated_dir="$(find "$CRASHPAD_SRC/out" -type d -name gen -print -quit 2>/dev/null || true)"
  if [[ -n "$generated_dir" ]]; then cp -R "$generated_dir" "$SDK_STAGE/include/"; fi
  find "$CRASHPAD_SRC/out" \( -name '*.a' -o -name '*.lib' \) -exec cp {} "$SDK_STAGE/lib/" \;
fi
cat > "$SDK_STAGE/manifest.json" <<JSON
{"schemaVersion":1,"sdkVersion":"$SDK_VERSION","platform":"$PLATFORM-$SDK_ARCH","arch":"$SDK_ARCH","crashpadRevision":"db44314646cbd0825a73b58dd2b7b5f4faca64a7","licenseMode":"bsd-compatible"}
JSON
cat > "$SDK_STAGE/cmake/CrashpadConfig.cmake" <<'CMAKE'
get_filename_component(PACKAGE_PREFIX_DIR "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
include("${CMAKE_CURRENT_LIST_DIR}/CrashpadTargets.cmake")
set(Crashpad_INCLUDE_DIR "${PACKAGE_PREFIX_DIR}/include")
set(Crashpad_HANDLER_PATH "${PACKAGE_PREFIX_DIR}/bin/crashpad_handler")
CMAKE
cat > "$SDK_STAGE/cmake/CrashpadConfigVersion.cmake" <<CMAKE
set(PACKAGE_VERSION "$SDK_VERSION")
set(PACKAGE_VERSION_COMPATIBLE TRUE)
set(PACKAGE_VERSION_EXACT TRUE)
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
  set_target_properties(Crashpad::Client PROPERTIES
    INTERFACE_INCLUDE_DIRECTORIES "${_crashpad_root}/include;${_crashpad_root}/include/crashpad;${_crashpad_root}/include/mini_chromium"
    INTERFACE_LINK_LIBRARIES "${_crashpad_libs}")
endif()
CMAKE
