$ErrorActionPreference = 'Stop'
if (!$env:SDK_ARCH -or !$env:CRASHPAD_SRC -or !$env:SDK_STAGE) { throw 'SDK_ARCH, CRASHPAD_SRC and SDK_STAGE are required' }
$out = Join-Path $env:CRASHPAD_SRC ("out\Release-" + $env:SDK_ARCH)
Set-Location $env:CRASHPAD_SRC
New-Item -ItemType Directory -Force $out | Out-Null
if (!(Get-Command gn -ErrorAction SilentlyContinue) -or !(Get-Command autoninja -ErrorAction SilentlyContinue)) { throw 'gn/autoninja unavailable; CI must provision depot_tools' }
$cpu = $env:SDK_ARCH
$gnArgs = 'target_os="win" target_cpu="' + $cpu + '" is_debug=false is_clang=true'
& gn gen $out --args=$gnArgs
& autoninja -C $out crashpad_handler
New-Item -ItemType Directory -Force (Join-Path $env:SDK_STAGE 'bin'), (Join-Path $env:SDK_STAGE 'lib'), (Join-Path $env:SDK_STAGE 'include') | Out-Null
Copy-Item (Join-Path $out 'crashpad_handler.exe') (Join-Path $env:SDK_STAGE 'bin')
