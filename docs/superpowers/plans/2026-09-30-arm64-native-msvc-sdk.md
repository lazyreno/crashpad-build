# ARM64 Native MSVC Crashpad SDK Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a Windows ARM64 Crashpad SDK built natively with MSVC 14.44.35207 so it links with VideoBee's unchanged ARM64 toolchain.

**Architecture:** ARM64 remains on the native Windows ARM64 runner. The Windows builder initializes the pinned HostARM64/ARM64 MSVC environment and invokes GN with MSVC and its configuration-specific dynamic CRT. The existing tagged full-matrix release publishes the new artifact index; the downstream pin moves only after it succeeds.

**Tech Stack:** GitHub Actions, Windows ARM64 runner, Visual Studio Build Tools v143 14.44.35207, PowerShell, GN/Ninja, Python unittest.

**Spec:** `docs/superpowers/specs/2026-09-30-arm64-native-msvc-sdk-design.md`

## Global Constraints

- Never cross-compile the ARM64 SDK; use `windows-11-vs2026-arm`.
- ARM64 producer compiler is MSVC `14.44.35207` at `HostARM64/ARM64`.
- Use `/MD` for release and `/MDd` for debug; do not alter x64 or macOS behavior.
- Publish all six artifacts and the index together; update downstream only from release metadata.

## Review Focus

- A runner without MSVC 14.44 must fail before GN generation.
- ARM64 must log and use `is_clang=false`.
- Debug must retain `/MDd`.
- The release must retain all six artifacts.
- VideoBee ARM64 packaging must link without `__std_*` unresolved externals.

---

### Task 1: Pin the native ARM64 producer toolchain

**Files:**
- Modify: `scripts/build-windows.ps1:1-18`
- Modify: `tests/test_sdk_contract.py:157-221`

**Interfaces:**
- Consumes: `SDK_ARCH`, `SDK_CONFIGURATION`, `CRASHPAD_SRC`.
- Produces: a validated ARM64 MSVC environment and MSVC GN arguments.

- [ ] **Step 1: Write failing producer-contract tests**

Require `VsDevCmd.bat` arguments `-host_arch=arm64`, `-arch=arm64`, and `-vcvars_ver=14.44.35207`; require a `HostARM64\\ARM64\\cl.exe` check and ARM64 GN arguments containing `is_clang=false` plus `/MD` or `/MDd`.

- [ ] **Step 2: Run the contract tests red**

Run `python tests/test_sdk_contract.py`. It must fail because the current builder uses clang and lacks native MSVC setup.

- [ ] **Step 3: Implement native MSVC setup**

For ARM64 only, locate Visual Studio with `vswhere`, import `VsDevCmd.bat` with the exact pinned arguments, reject a compiler outside the required path, and generate GN files using `is_clang=false`. Preserve x64 behavior and the existing configuration-derived CRT option.

- [ ] **Step 4: Run the contract tests green**

Run `python tests/test_sdk_contract.py`. All tests must pass.

- [ ] **Step 5: Commit**

Commit `scripts/build-windows.ps1` and `tests/test_sdk_contract.py` with message `fix: build arm64 crashpad with pinned native msvc`.

### Task 2: Make the CI runner and toolchain contract observable

**Files:**
- Modify: `.github/workflows/build.yml:20-94`
- Modify: `config/platform-matrix.json:17-32`
- Modify: `tests/test_sdk_contract.py:145-175`

**Interfaces:**
- Consumes: Task 1's pinned producer contract.
- Produces: native ARM64 runner and compiler diagnostics before building.

- [ ] **Step 1: Write failing workflow-contract tests**

Require the dedicated ARM64 runner label and diagnostics for runner architecture, resolved compiler path, and MSVC version.

- [ ] **Step 2: Run tests red**

Run `python tests/test_sdk_contract.py`. It must fail because diagnostics are absent.

- [ ] **Step 3: Implement CI diagnostics**

Keep ARM64 matrix entries on `windows-11-vs2026-arm`; add pre-build diagnostics without changing macOS or x64 entries.

- [ ] **Step 4: Run the full contract suite green**

Run `python tests/test_sdk_contract.py`. All tests must pass.

- [ ] **Step 5: Commit**

Commit `.github/workflows/build.yml`, `config/platform-matrix.json`, and `tests/test_sdk_contract.py` with message `ci: verify native arm64 msvc crashpad builds`.

### Task 3: Publish the replacement SDK

**Files:**
- Modify: `config/sdk-version.json:1-4`

**Interfaces:**
- Consumes: passing workflow from Tasks 1-2.
- Produces: a new version-tagged release with six archives, SHA-256 files, and an artifact index.

- [ ] **Step 1: Set the next unique SDK version**

Update `config/sdk-version.json` while retaining `licenseMode`.

- [ ] **Step 2: Validate locally**

Run `python tests/test_sdk_contract.py`. All tests must pass.

- [ ] **Step 3: Commit and push the release branch**

Commit the version with message `release: prepare arm64 native msvc crashpad sdk`, then push `fix/arm64-native-msvc-sdk`.

- [ ] **Step 4: Validate branch CI, merge, tag, and publish**

Require all ARM64 release/debug, x64 release/debug, and macOS arm64/x64 jobs to pass. Create a tag exactly matching `v<SDK_VERSION>` only after merge, then verify the release contains all archives, checksums, and `artifact-index.json`.

### Task 4: Pin the consumer and validate VideoBee

**Files:**
- Modify: `C:/se-desktop/desktop-base/cmake/crashpad/CrashpadSdkArtifacts.cmake:1-4`

**Interfaces:**
- Consumes: published version, release tag, and artifact-index SHA-256.
- Produces: a compatible Crashpad selection for VideoBee ARM64 packaging.

- [ ] **Step 1: Write a failing desktop-base pin contract**

Require the published SDK version and index hash; do not invent the hash.

- [ ] **Step 2: Update the downstream pin from release metadata**

Replace version, tag, and SHA-256 in `CrashpadSdkArtifacts.cmake`.

- [ ] **Step 3: Run the desktop-base Crashpad contract test**

Confirm the new index selects the Windows ARM64 release SDK.

- [ ] **Step 4: Run VideoBee local ARM64 packaging**

Run `C:/se-desktop/videobee-desktop/scripts/pack` with Local, Release, ARM64. `VideoBee.exe` must link without the prior `__std_*` unresolved externals.
