$ErrorActionPreference = 'Stop'
if (!$env:SDK_ARCH -or !$env:CRASHPAD_SRC) { throw 'SDK_ARCH and CRASHPAD_SRC are required' }
$out = Join-Path $env:CRASHPAD_SRC ("out\Release-" + $env:SDK_ARCH)
Set-Location $env:CRASHPAD_SRC
New-Item -ItemType Directory -Force $out | Out-Null
if (!(Get-Command gn -ErrorAction SilentlyContinue) -or !(Get-Command autoninja -ErrorAction SilentlyContinue)) { throw 'gn/autoninja unavailable; CI must provision depot_tools' }
$cpu = $env:SDK_ARCH
$gnArgs = 'target_os="win" target_cpu="' + $cpu + '" is_debug=false is_clang=true'
& gn gen $out --args=$gnArgs
& autoninja -C $out crashpad_handler
if ($env:CRASHPAD_RUN_UPSTREAM_TESTS -eq 'true') {
    $testTargets = @(
        'crashpad_client_test',
        'crashpad_handler_test',
        'crashpad_minidump_test',
        'crashpad_snapshot_test',
        'crashpad_test_test',
        'crashpad_util_test'
    )
    & autoninja -C $out $testTargets
    if ($LASTEXITCODE -ne 0) { throw 'Crashpad upstream test targets failed to build' }
    & tzutil /s 'Pacific Standard Time'
    if ($LASTEXITCODE -ne 0) { throw 'Failed to set the upstream test time zone' }
    $env:CRASHPAD_TEST_DATA_ROOT = $env:CRASHPAD_SRC
    foreach ($testTarget in $testTargets) {
        & (Join-Path $out "$testTarget.exe")
        if ($LASTEXITCODE -ne 0) { throw "Crashpad upstream test failed: $testTarget" }
    }
}
