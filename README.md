# crashpad-build

Reproducible Crashpad SDK artifacts for macOS arm64/x64 and Windows arm64/x64.

Each artifact contains Crashpad headers, static libraries, `crashpad_handler`,
CMake metadata, the upstream license, and a target manifest. Source revisions
are pinned in `config/source-lock.json`; manifests and the artifact index use
`os` and `arch` as separate target fields. The release workflow validates the
staged layout and each handler's minimum supported system version before
publishing it.
