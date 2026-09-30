# ARM64 Native MSVC Crashpad SDK Design

## Goal

Publish a new Windows ARM64 Crashpad SDK that links with VideoBee's fixed
MSVC v143 toolset (`14.44.35207`) without changing the application's build
toolchain or relying on x64-to-ARM64 cross compilation for the SDK producer.

## Constraints

- Windows ARM64 SDK builds run on a native Windows ARM64 runner.
- The producer selects MSVC `14.44.35207` with `HostARM64/ARM64` tools.
- Windows release SDKs use the dynamic CRT (`/MD`); debug SDKs use `/MDd`.
- macOS and Windows x64 artifacts remain unchanged.
- A release remains all-or-nothing: it publishes all six matrix artifacts and
  an artifact index under a new version tag.
- The downstream `desktop-base` pin is updated only after the release assets
  and index have passed validation.

## Design

The ARM64 matrix entries retain their dedicated native ARM64 runner label. The
Windows build script initializes the exact MSVC v143 toolset from Visual
Studio, verifies its `HostARM64/ARM64` compiler path and compiler version, and
generates GN files with MSVC rather than clang. Its existing release/debug CRT
selection remains `/MD` and `/MDd`.

The workflow fails before compiling if the native ARM64 runner does not expose
the required toolset. This prevents accidentally publishing an SDK built with
a newer C++ runtime whose link helpers are unavailable to downstream MSVC
14.44 consumers.

The test suite verifies the ARM64 runner/toolset contract and the Windows GN
arguments. A release tag with the next available SDK version triggers the
existing full matrix, artifact-layout validation, SHA-256 index generation,
and GitHub Release publishing. After it succeeds, `desktop-base` updates its
Crashpad artifact-index version, release tag, and SHA-256 pin; VideoBee ARM64
packaging is the downstream acceptance test.

## Failure Handling

- Missing native ARM64 runner or MSVC 14.44: fail before GN generation; do not
  fall back to a cross compiler or a newer toolset.
- Native build or upstream Crashpad tests fail: no release tag is created.
- Any artifact validation or publishing failure: leave the downstream pin at
  the previous release.
- VideoBee ARM64 link failure after the new release: retain the new diagnostics
  and investigate the producer/consumer library directives before another
  release.

## Acceptance Criteria

1. ARM64 SDK build logs identify a `HostARM64/ARM64` MSVC `14.44.35207` toolset.
2. Windows ARM64 artifacts are produced on the native ARM64 runner with
   `is_clang=false` and the configuration-appropriate dynamic CRT.
3. All six release artifacts and `artifact-index.json` are published under a
   new version tag.
4. `desktop-base` consumes the new artifact index and VideoBee's local ARM64
   package links past the previous `__std_*` unresolved externals.
