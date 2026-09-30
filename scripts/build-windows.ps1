$ErrorActionPreference = 'Stop'
if (!$env:SDK_ARCH -or !$env:SDK_CONFIGURATION -or !$env:CRASHPAD_SRC) { throw 'SDK_ARCH, SDK_CONFIGURATION and CRASHPAD_SRC are required' }

function Initialize-NativeArm64Msvc {
    $toolsetVersion = '14.44.35207'
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (!(Test-Path -LiteralPath $vswhere)) { throw "vswhere.exe was not found: $vswhere" }
    $installation = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
    if (!$installation) { throw 'Visual Studio Build Tools with C++ tools was not found.' }
    $vsDevCmd = Join-Path $installation 'Common7\Tools\VsDevCmd.bat'
    $expectedCompiler = Join-Path $installation "VC\Tools\MSVC\$toolsetVersion\bin\HostARM64\ARM64\cl.exe"
    if (!(Test-Path -LiteralPath $vsDevCmd)) { throw "VsDevCmd.bat was not found: $vsDevCmd" }
    if (!(Test-Path -LiteralPath $expectedCompiler)) { throw "Native ARM64 MSVC $toolsetVersion was not found: $expectedCompiler" }

    $environmentLines = & cmd.exe /d /s /c "`"$vsDevCmd`" -host_arch=arm64 -arch=arm64 -vcvars_ver=$toolsetVersion >nul && set"
    if ($LASTEXITCODE -ne 0) { throw "Failed to initialize native ARM64 MSVC $toolsetVersion" }
    foreach ($line in $environmentLines) {
        if ($line -match '^(?<name>[^=]+)=(?<value>.*)$') {
            Set-Item -LiteralPath "Env:$($Matches.name)" -Value $Matches.value
        }
    }

    $compiler = (Get-Command cl.exe -ErrorAction Stop).Source
    if ((Resolve-Path -LiteralPath $compiler).Path -ine (Resolve-Path -LiteralPath $expectedCompiler).Path) {
        throw "Expected native ARM64 compiler $expectedCompiler, got $compiler"
    }
    Write-Host "[BUILD] Native ARM64 MSVC: $compiler"
}

$buildConfiguration, $isDebug, $runtimeLibrary = switch ($env:SDK_CONFIGURATION) {
    'release' { 'Release', 'false', '/MD' }
    'debug' { 'Debug', 'true', '/MDd' }
    default { throw "Unsupported SDK configuration: $($env:SDK_CONFIGURATION)" }
}
$out = Join-Path $env:CRASHPAD_SRC ("out\" + $buildConfiguration + "-" + $env:SDK_ARCH)
Set-Location $env:CRASHPAD_SRC
New-Item -ItemType Directory -Force $out | Out-Null
if (!(Get-Command gn -ErrorAction SilentlyContinue) -or !(Get-Command autoninja -ErrorAction SilentlyContinue)) { throw 'gn/autoninja unavailable; CI must provision depot_tools' }
$cpu = $env:SDK_ARCH
if ($cpu -eq 'arm64') {
    Initialize-NativeArm64Msvc
    $compilerMode = 'is_clang=false'
} else {
    $compilerMode = 'is_clang=true'
}
$gnArgs = 'target_os="win" target_cpu="' + $cpu + '" is_debug=' + $isDebug + ' ' + $compilerMode + ' extra_cflags="' + $runtimeLibrary + '"'
& gn gen $out --args=$gnArgs
& autoninja -C $out crashpad_handler client client:common
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
