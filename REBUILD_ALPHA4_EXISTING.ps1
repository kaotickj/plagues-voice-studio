<#
Rebuild the v0.3 Windows executable using EXISTING .venv-build.
No package/model downloads, no compression, no installer. Run in project root.
Retained for compatibility with previous alpha4 source layouts; it also accepts v0.3.0 and v0.3.0rc1.
#>
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$python = Join-Path $root '.venv-build\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Missing .venv-build: apply alpha4 to the previously built experimental directory, or set up a new build environment.'
}
$versionFile = Join-Path $root 'src\chatterbox_studio\__init__.py'
if ((Get-Content -LiteralPath $versionFile -Raw) -notmatch '0\.3\.0(?:-alpha4)?') {
    throw 'Expected v0.3.0 (or older alpha4) source. Update the checkout before rebuilding.'
}
$free = (Get-PSDrive -Name (Split-Path -Qualifier $root).TrimEnd(':')).Free
Write-Host ('Free build-drive disk space: {0:N1} GB' -f ($free / 1GB))
if ($free -lt 8GB) { Write-Warning 'Low disk space: PyInstaller needs temporary build space.' }
Write-Host 'Rebuilding the existing v0.3 app WITHOUT pip, model downloads or ZIP packaging...'
& $python -m PyInstaller --noconfirm ChatterboxStudio.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller rebuild failed. Check space and installed build packages.' }
$exe = Join-Path $root 'dist\PlaguesVoiceStudio030Experimental\PlaguesVoiceStudio030Experimental.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "Executable missing: $exe" }
New-Item -ItemType Directory -Force -Path (Join-Path $root 'build') | Out-Null
foreach ($mode in @('--self-test','--ui-self-test')) {
    $report = if ($mode -eq '--self-test') { 'build\alpha4-runtime-test.json' } else { 'build\alpha4-ui-test.json' }
    $dest = Join-Path $root $report
    if (Test-Path $dest) { Remove-Item -LiteralPath $dest -Force }
    Write-Host "Running $mode ..."
    $p = Start-Process -FilePath $exe -ArgumentList @($mode, ('"' + $dest + '"')) -Wait -PassThru
    if (-not (Test-Path $dest)) { throw "No self-test report: $dest (exit $($p.ExitCode))" }
    $check = Get-Content -LiteralPath $dest -Raw | ConvertFrom-Json
    if ($p.ExitCode -ne 0 -or $check.status -ne 'passed') {
        throw "Smoke test failed; inspect $dest"
    }
    if ($mode -eq '--ui-self-test' -and $check.version -notin @('0.3.0rc1', '0.3.0', '0.3.0-alpha4')) {
        throw "Incorrect frozen version: $($check.version)"
    }
    Write-Host "PASSED: $mode"
}
Write-Host "v0.3 executable ready: $exe"
Write-Host 'Launch the above EXE directly; old desktop shortcuts may still launch an older build.'
