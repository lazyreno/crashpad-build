# Crashpad Cloud Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build reproducible Crashpad SDK archives for macOS arm64/x64 and Windows arm64/x64 in GitHub Actions, publish immutable Releases, and integrate the package with audiocut-desktop.

**Architecture:** Declaration-driven producer modeled on `/Users/zhao/app/ffmpeg-base`: pinned source inputs and platform matrix feed a prepare job; four platform jobs build, stage, validate, archive, and checksum one SDK each; a publish job emits a Release and artifact index. The SDK exports CMake targets and compatibility variables consumed by desktop-base/audiocut.

**Tech Stack:** GitHub Actions, GN/Ninja, Chromium depot_tools, MSVC/clang, Bash, PowerShell, Python, CMake, GitHub Releases.

**Spec:** `docs/superpowers/specs/2026-09-14-crashpad-cloud-build-design.md`

## Global Constraints

- Build exactly `macos-arm64`, `macos-x64`, `windows-arm64`, and `windows-x64`.
- Pin Crashpad, Chromium/depot_tools inputs, SDK version, and source checksums.
- Windows arm64 is cross-built on an x64 runner and is never executed there.
- Published archives are immutable; changed inputs require a new SDK version.
- Official clients consume the packaged CMake SDK, never developer-machine Crashpad.
- Backend upload, symbolication, and crash-service deployment are out of scope.

### Task 1: Declare versions, locks, and matrix

**Files:** Create `config/sdk-version.json`, `config/platform-matrix.json`, `config/source-lock.json`, `scripts/generate-github-matrix.py`, `tests/python/test_generate_github_matrix.py`.

- [ ] Add JSON declarations for SDK version, Crashpad/depot_tools revisions, checksums, runner, architecture, archive extension, and minimum system versions.
- [ ] Implement deterministic matrix output and rejection of duplicate keys or unsupported architectures.
- [ ] Add tests for all four platforms and invalid declarations; run `python3 -m unittest discover -s tests/python -v`.

### Task 2: Stage SDK and generate metadata

**Files:** Create `scripts/stage-sdk.sh`, `templates/manifest.json.in`, `scripts/generate-artifact-index.py`, `tests/python/test_generate_artifact_index.py`.

- [ ] Stage `bin`, `include`, `lib`, `cmake`, `symbols`, `licenses`, and `manifest.json` under `crashpad-sdk-v{sdkVersion}-{platform}`.
- [ ] Generate manifest from declarations and staged file metadata, including source revision and checksum.
- [ ] Generate deterministic `artifact-index.json` with platform, architecture, URL, SHA256, size, SDK version, and source metadata.
- [ ] Test missing files, manifest/matrix mismatch, and stable ordering.

### Task 3: Add CMake package

**Files:** Create `cmake-package/CrashpadConfig.cmake.in`, `cmake-package/CrashpadTargets.cmake.in`, `cmake-package/CrashpadRuntime.cmake`, `tests/cmake/test_crashpad_package.cmake`.

- [ ] Export `Crashpad::Client` and `Crashpad::Handler` with paths relative to the extracted SDK.
- [ ] Expose `CRASHPAD_INCLUDE_DIR`, `CRASHPAD_INCLUDE_DIRS`, `CRASHPAD_LIBRARIES`, and `CRASHPAD_HANDLER_PATH` compatibility values.
- [ ] Configure a minimal consumer in the CMake test and verify include, library, target, and handler resolution.

### Task 4: Build macOS SDKs

**Files:** Create `scripts/build-macos.sh`, `tests/python/test_validate_macos_sdk.py`.

- [ ] Fetch pinned depot_tools and Crashpad dependencies with revision/checksum verification.
- [ ] Generate GN args for arm64 and x64, build with Ninja, and stage required headers, static libraries, handler, symbols, licenses, and CMake files.
- [ ] Validate staged Mach-O files with `file`, `otool`, and `vtool`; reject architecture or minimum-system-version mismatches.
- [ ] Run both architecture builds in Actions before release acceptance.

### Task 5: Build Windows SDKs

**Files:** Create `scripts/build-windows.ps1`, `tests/python/test_validate_windows_sdk.py`.

- [ ] Bootstrap pinned depot_tools and Visual Studio MSVC/clang environment.
- [ ] Generate GN args for x64 and arm64, build with Ninja, and stage `.lib`, `.exe`, headers, symbols, licenses, and CMake files.
- [ ] Validate PE headers with `dumpbin /headers`; reject target-architecture mismatches.
- [ ] Record ARM64 runtime validation on ARM64 Windows as a release acceptance check.

### Task 6: Validate archives and release rules

**Files:** Create `scripts/validate-sdk-layout.py`, `tests/python/test_validate_sdk_layout.py`, `tests/cmake/test_release_workflow.cmake`.

- [ ] Validate required paths, executable presence, architecture metadata, manifest consistency, licenses, and absence of build/cache files.
- [ ] Validate tag format, SDK-version matching, and refusal to overwrite an existing release.
- [ ] Run Python and CMake tests in a clean checkout.

### Task 7: Add GitHub Actions workflow

**Files:** Create `.github/workflows/build.yml`, `ci/README.md`.

- [ ] Add `prepare-matrix`, `build-sdk`, and `publish-release` jobs with `fail-fast: false`, bounded timeouts, and read-only contents permission.
- [ ] Cache dependency checkouts using revision-keyed keys; never cache staged release output.
- [ ] Upload per-platform artifacts on `main`; publish archives, SHA256 files, and `artifact-index.json` for manual runs and matching `v*` tags.
- [ ] Reject manual releases off `main`, mismatched tags, and duplicate SDK releases.
- [ ] Document runners, artifact names, release triggers, and ARM64 runtime limitation.

### Task 8: Integrate audiocut-desktop

**Files:** Modify the existing audiocut SDK declaration/download and CMake integration files; add the client Crashpad declaration beside its current FFmpeg declaration.

- [ ] Resolve the platform entry from `artifact-index.json`, download the archive, and verify SHA256.
- [ ] Pass the extracted SDK to CMake through the package and desktop-base compatibility variables.
- [ ] Package `crashpad_handler` with the existing macOS/Windows packaging scripts.
- [ ] Run `cmake --fresh`, build, `CommonCrashCaptureContract`, and a controlled crash that creates a pending report.

### Task 9: Release acceptance

**Files:** Create `docs/release-process.md` and update `ci/README.md`.

- [ ] Publish a protected `v{sdkVersion}` tag and verify all eight archive/checksum assets plus `artifact-index.json`.
- [ ] Verify macOS artifacts on matching hosts, Windows x64 on Windows, and Windows arm64 on ARM64 Windows hardware or VM.
- [ ] Record workflow run, commit, source revisions, checksums, and client integration result.
- [ ] Update audiocut to the immutable Release URL and expected SDK version.
