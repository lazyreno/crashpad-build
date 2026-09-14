#!/usr/bin/env bash
set -euo pipefail
: "${SDK_STAGE:?}"; : "${SDK_VERSION:?}"; : "${PLATFORM:?}"
mkdir -p "$SDK_STAGE/cmake" "$SDK_STAGE/licenses"
cat > "$SDK_STAGE/manifest.json" <<JSON
{"schemaVersion":1,"sdkVersion":"$SDK_VERSION","platform":"$PLATFORM","crashpadRevision":"db44314646cbd0825a73b58dd2b7b5f4faca64a7","licenseMode":"bsd-compatible"}
JSON
cat > "$SDK_STAGE/cmake/CrashpadConfig.cmake" <<'CMAKE'
include("${CMAKE_CURRENT_LIST_DIR}/CrashpadTargets.cmake")
set(CRASHPAD_INCLUDE_DIR "${PACKAGE_PREFIX_DIR}/include")
set(CRASHPAD_INCLUDE_DIRS "${PACKAGE_PREFIX_DIR}/include")
set(CRASHPAD_HANDLER_PATH "${PACKAGE_PREFIX_DIR}/bin/crashpad_handler")
CMAKE
cat > "$SDK_STAGE/cmake/CrashpadTargets.cmake" <<'CMAKE'
if(NOT TARGET Crashpad::Client)
 add_library(Crashpad::Client INTERFACE IMPORTED)
 set_target_properties(Crashpad::Client PROPERTIES INTERFACE_INCLUDE_DIRECTORIES "${PACKAGE_PREFIX_DIR}/include")
endif()
CMAKE
