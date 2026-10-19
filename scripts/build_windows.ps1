<#
.SYNOPSIS
  Build a bundled Windows portable package and Inno Setup installer.
.DESCRIPTION
  Build machine: Windows x64, Python 3.12, Git, internet to download weights,
  and Inno Setup 6 for the optional conventional installer.
  -FullOffline downloads AND validates all four models, then bundles an
  offline-only policy marker so runtime will never silently download weights.
  -Slim builds a model-on-demand setup without bundling existing model weights.
  -SkipModels can be used with -FullOffline ONLY if all weights were previously
  downloaded to models/. The preflight validation will still run.
.EXAMPLE
  .\scripts\build_windows.ps1 -FullOffline
.EXAMPLE
  .\scripts\build_windows.ps1 -FullOffline -SkipModels
.EXAMPLE
  .\scripts\build_windows.ps1 -Slim
.EXAMPLE
  .\scripts\build_windows.ps1 -Models nano
#>
param(
    [ValidateSet('nano','turbo','english','multilingual-v3')]
    [string[]]$Models = @('nano'),
    [switch]$FullOffline,
    [switch]$Slim,
    [switch]$SkipModels,
    [switch]$SkipInstaller,
    [switch]$SkipDependencies
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root

function Assert-Success([string]$message) {
    if ($LASTEXITCODE -ne 0) { throw $message }
}

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw 'The Windows installer must be built on 64-bit Windows.'
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'Git is required on the BUILD machine to install upstream Chatterbox.'
}
if ($Slim -and ($FullOffline -or $SkipModels)) { throw 'Slim cannot be combined with FullOffline or SkipModels.' }
if ($Slim) { Write-Host 'Building small installer: models are installed later through Model Manager.' }
if ($FullOffline) {
    $Models = @('nano','turbo','english','multilingual-v3')
    Write-Host 'Building STRICT FULL-OFFLINE edition with ALL FOUR Chatterbox models.'
}

if (-not (Test-Path '.venv-build\Scripts\python.exe')) {
    py -3.12 -m venv .venv-build
    Assert-Success 'Could not create venv. Install 64-bit Python 3.12.'
}
$python = Join-Path $root '.venv-build\Scripts\python.exe'
$pythonVersion = & $python -c 'import sys; print("%d.%d" % sys.version_info[:2])'
Assert-Success 'Could not inspect the build interpreter'
if ($pythonVersion -ne '3.12') { throw 'The validated release lock requires Python 3.12. Use a separate Python 3.12 build environment.' }
$bootstrapPath = $env:PATH
try {
    # uv_build locates its executable through PATH, even when pip uses an absolute interpreter.
    $env:PATH = (Split-Path -Parent $python) + ';' + $bootstrapPath
if (-not $SkipDependencies) {
    & $python -m pip install --no-deps 'pip==26.2.1' 'setuptools==84.0.0' 'wheel==0.48.0' 'packaging==26.3' 'uv_build==0.12.7'
    Assert-Success 'pip bootstrap failed'
    & $python -m pip install --no-deps --no-build-isolation --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-release.txt
    Assert-Success 'Locked dependency installation failed'
    & $python -m pip install --no-deps --no-build-isolation -e '.[build,test]'
    Assert-Success 'Project installation failed'
}
} finally { $env:PATH = $bootstrapPath }
& $python -m pip check
Assert-Success 'Installed build dependencies are inconsistent'
$expectedVersion = & $python -c 'from chatterbox_studio import __version__; print(__version__)'
# Release archives must never bypass the complete regression suite.
$previousQt = $env:QT_QPA_PLATFORM
try {
    $env:QT_QPA_PLATFORM = 'offscreen'
    & $python -m pytest -q
    Assert-Success 'Regression tests failed; packaging aborted'
} finally { $env:QT_QPA_PLATFORM = $previousQt }

# Remove stale strict mode marker before preparing a new build.
$marker = Join-Path $root 'models\offline-bundle.json'
if (Test-Path $marker) { Remove-Item $marker -Force }
if (-not $SkipModels -and -not $Slim) {
    & $python scripts\download_models.py @Models
    Assert-Success 'Model download or validation failed; no installer produced.'
}
if ($FullOffline) {
    & $python scripts\verify_models.py --all --root models --write-marker
    Assert-Success 'Strict offline preflight failed. Cannot release an incomplete bundle.'
}

# Never reuse previous frozen Python modules. Source edits do not change a built EXE.
if (Test-Path 'dist\PlaguesVoiceStudio030Experimental') {
    $cleanTarget = (Resolve-Path -LiteralPath 'dist\PlaguesVoiceStudio030Experimental').Path
    $expectedTarget = Join-Path $root 'dist\PlaguesVoiceStudio030Experimental'
    if ($cleanTarget -ne $expectedTarget) { throw 'Unexpected build cleanup target.' }
    Remove-Item -LiteralPath $cleanTarget -Recurse -Force
}
$oldSlim = [Environment]::GetEnvironmentVariable('PVS_SLIM_BUILD')
$oldBuildPath = $env:PATH
try {
    if ($Slim) { $env:PVS_SLIM_BUILD = '1' } else { Remove-Item Env:PVS_SLIM_BUILD -ErrorAction SilentlyContinue }
    $env:PATH = (Split-Path -Parent $python) + ';' + (Join-Path $env:SystemRoot 'System32') + ';' + $env:SystemRoot
    & $python -m PyInstaller --clean --noconfirm ChatterboxStudio.spec
    Assert-Success 'PyInstaller build failed'
} finally {
    $env:PATH = $oldBuildPath
    if ($null -eq $oldSlim) { Remove-Item Env:PVS_SLIM_BUILD -ErrorAction SilentlyContinue }
    else { $env:PVS_SLIM_BUILD = $oldSlim }
}

# Smoke-test the actual frozen executable, not just the source venv. This
# catches missing importlib.metadata *.dist-info directories, such as the
# Transformers/requests issue, BEFORE compression or installer generation.
$exe = Join-Path $root 'dist\PlaguesVoiceStudio030Experimental\PlaguesVoiceStudio030Experimental.exe'
$report = Join-Path $root 'build\frozen-smoke-test.json'
if (Test-Path $report) { Remove-Item $report -Force }
Write-Host 'Testing frozen runtime and dependency metadata...'
$smoke = Start-Process -FilePath $exe -ArgumentList @('--self-test', ('"' + $report + '"')) -Wait -PassThru -WindowStyle Hidden
if (-not (Test-Path $report)) {
    throw "Frozen self-test did not produce a report (exit code $($smoke.ExitCode))."
}
$smokeReport = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
if ($smoke.ExitCode -ne 0 -or $smokeReport.status -ne 'passed') {
    $details = ($smokeReport.errors | Out-String).Trim()
    throw "Frozen application self-test failed. Fix before packaging. Details:`n$details"
}
Write-Host 'Frozen runtime self-test PASSED (all checked package metadata and model imports).'

# Exercise the ACTUAL packaged Qt main window and its Export Library.
# A basic dependency test does not catch NameError in ExportBrowser._build.
$uiReport = Join-Path $root 'build\frozen-ui-smoke-test.json'
if (Test-Path $uiReport) { Remove-Item -LiteralPath $uiReport -Force }
Write-Host 'Smoke-testing packaged Qt GUI initialization...'
$uiSmoke = Start-Process -FilePath $exe -ArgumentList @('--ui-self-test', ('"' + $uiReport + '"')) -Wait -PassThru -WindowStyle Hidden
if (-not (Test-Path $uiReport)) {
    throw "Frozen GUI test did not produce a report (exit code $($uiSmoke.ExitCode)). The installer was NOT created."
}
$uiResult = Get-Content -LiteralPath $uiReport -Raw | ConvertFrom-Json
if ($uiSmoke.ExitCode -ne 0 -or $uiResult.status -ne 'passed' -or $uiResult.version -ne $expectedVersion) {
    $details = ($uiResult.errors | Out-String).Trim()
    throw "Frozen GUI startup test failed. Installer not created. Details:`n$details"
}
Write-Host 'Frozen Qt main-window test PASSED.'
if ($Slim) {
    $distModels = Join-Path $root 'dist\PlaguesVoiceStudio030Experimental\_internal\models'
    if (Test-Path $distModels) {
        $weights = @(Get-ChildItem -LiteralPath $distModels -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in @('.safetensors', '.pt', '.bin') })
        if ($weights.Count -gt 0) { throw 'Slim build accidentally included Chatterbox weight files; abort packaging.' }
    }
}

if ($FullOffline) {
    # PyInstaller onedir locates collected data under dist\App\_internal\.
    & $python scripts\verify_models.py --all --root dist\PlaguesVoiceStudio030Experimental\_internal\models --require-marker
    Assert-Success 'Frozen application is missing model data. Packaging aborted.'
}

New-Item -ItemType Directory -Force artifacts | Out-Null
$filename = if ($FullOffline) { 'PlaguesVoiceStudio-FullOffline-Portable.zip' } elseif ($Slim) { 'PlaguesVoiceStudio-Slim-Portable.zip' } else { 'PlaguesVoiceStudio-Portable.zip' }
$portable = Join-Path $root ('artifacts\' + $filename)
if (Test-Path $portable) { Remove-Item $portable -Force }
Compress-Archive -Path 'dist\PlaguesVoiceStudio030Experimental' -DestinationPath $portable -CompressionLevel Optimal
Write-Host "Portable distribution: $portable"

if (-not $SkipInstaller) {
    $iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if (-not $iscc) {
        $candidate = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
        if (Test-Path $candidate) { $iscc = @{ Source=$candidate } }
    }
    if (-not $iscc) {
        throw 'Inno Setup 6 not found. Install it for a release installer or explicitly request -SkipInstaller for a portable-only build.'
    } else {
        if (Test-Path 'dist-installer') {
            # Avoid copying stale BIN slices from earlier builds.
            $installerClean = (Resolve-Path -LiteralPath 'dist-installer').Path
            if ($installerClean -ne (Join-Path $root 'dist-installer')) { throw 'Unexpected installer cleanup target.' }
            Remove-Item -LiteralPath $installerClean -Recurse -Force
        }
        & $iscc.Source installer.iss
        Assert-Success 'Inno Setup compilation failed'
        # Prevent stale multi-disk installers from leaking into a new artifact.
        Get-ChildItem artifacts -Filter 'PlaguesVoiceStudio-Setup-*' -File |
            Remove-Item -Force

        # Inno Setup 6.5.2+ builds a self-contained EXE under ~4 GB without
        # media slices. Abort if disk spanning returns or the build is incomplete.
        $setups = @(Get-ChildItem dist-installer -Filter 'PlaguesVoiceStudio-Setup-*.exe' -File)
        $slices = @(Get-ChildItem dist-installer -Filter '*.bin' -File)
        if ($setups.Count -ne 1 -or $slices.Count -ne 0) {
            throw "Expected ONE self-contained setup EXE and ZERO BIN slices, found $($setups.Count) EXE(s) and $($slices.Count) slice(s)."
        }
        if ($setups[0].Length -ge 4000000000) {
            throw "Setup EXE is over the supported single-file size budget. Use a smaller model bundle or redesign delivery, never silently enable disk spanning."
        }
        Copy-Item -LiteralPath $setups[0].FullName -Destination artifacts\ -Force
        Write-Host "Standalone installer: $($setups[0].Name) ($($setups[0].Length) bytes). No extra disks or BIN files required."
    }
}
Write-Host 'Done. Slim installs require a one-time user-approved model download in Model Manager; FullOffline includes all Chatterbox weights.'
