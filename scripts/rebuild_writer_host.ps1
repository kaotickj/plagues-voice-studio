<# Rebuild the complete slim host in a separate portable directory using an installed build environment. #>
param([string]$PythonExecutable = '', [string]$OutputDirectory = 'dist\WriterPluginPreview',
      [string]$ReportDirectory = 'artifacts\writer-host-build',
      [string]$ArchiveName = 'PlaguesVoiceStudio-WriterPlugin-Portable.zip',
      [string]$WorkDirectory = 'build\writer-plugin-host', [switch]$Incremental)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $PythonExecutable) { $PythonExecutable = Join-Path $repo '.venv-build\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $PythonExecutable)) { throw 'Install the complete host build dependencies in .venv-build first.' }
$output = [IO.Path]::GetFullPath((Join-Path $repo $OutputDirectory))
if (-not $output.StartsWith($repo + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Build output must stay inside this checkout.'
}
$work = [IO.Path]::GetFullPath((Join-Path $repo $WorkDirectory))
if (-not $work.StartsWith($repo + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Build work must stay inside this checkout.'
}
$reports = [IO.Path]::GetFullPath((Join-Path $repo $ReportDirectory))
if (-not $reports.StartsWith($repo + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Reports must stay inside this checkout.'
}
if ([IO.Path]::GetFileName($ArchiveName) -ne $ArchiveName) { throw 'ArchiveName must be a filename.' }
New-Item -ItemType Directory -Force -Path $reports | Out-Null
$savedPath = $env:PATH; $savedSlim = $env:PVS_SLIM_BUILD; $savedQt = $env:QT_QPA_PLATFORM
Push-Location $repo
try {
    # Prevent unrelated developer-tool DLLs from entering the frozen package.
    $env:PATH = (Split-Path -Parent $PythonExecutable) + ';' + (Join-Path $env:SystemRoot 'System32') + ';' + $env:SystemRoot
    $env:PVS_SLIM_BUILD = '1'; $env:QT_QPA_PLATFORM = 'offscreen'
    # Refresh project bytecode before analysis after fast local source edits.
    & $PythonExecutable -m compileall -q -f src\chatterbox_studio src\plagued_ai plugins\writer_core
    if ($LASTEXITCODE -ne 0) { throw 'Project bytecode validation failed.' }
    $bundleArguments = @('--noconfirm', '--distpath', $output, '--workpath', $work)
    if (-not $Incremental) { $bundleArguments += '--clean' }
    & $PythonExecutable -m PyInstaller @bundleArguments ChatterboxStudio.spec
    if ($LASTEXITCODE -ne 0) { throw 'Voice Studio PyInstaller build failed.' }
    $folder = Join-Path $output 'PlaguesVoiceStudio030Experimental'
    $exe = Join-Path $folder 'PlaguesVoiceStudio030Experimental.exe'
    foreach ($mode in @('--self-test', '--ui-self-test')) {
        $report = Join-Path $reports ($mode.TrimStart('-') + '.json')
        if (Test-Path -LiteralPath $report) { Remove-Item -LiteralPath $report }
        $proc = Start-Process -FilePath $exe -ArgumentList @($mode, ('"' + $report + '"')) -PassThru -WindowStyle Hidden
        if (-not $proc.WaitForExit(180000)) { $proc.Kill(); throw "$mode timed out." }
        if ($proc.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $report)) { throw "$mode failed; inspect $reports." }
        $result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
        if ($result.status -ne 'passed') { throw "$mode failed: $($result.errors -join [Environment]::NewLine)" }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $folder '_internal\plugins\promotional-writer\plugin.json'))) {
        throw 'Generic writer plugin is missing from the package.'
    }
    if (Test-Path -LiteralPath (Join-Path $folder '_internal\plugins\dj-writer')) { throw 'Branded standalone must not be bundled.' }
    & $PythonExecutable scripts\verify_frozen_source.py --exe $exe --report (Join-Path $reports 'source-package-check.json')
    if ($LASTEXITCODE -ne 0) { throw 'Packaged Python/plugin files do not match source.' }
    $archive = Join-Path $reports $ArchiveName
    Compress-Archive -LiteralPath $folder -DestinationPath $archive -Force
    $hash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $([IO.Path]::GetFileName($archive))" | Set-Content (Join-Path $reports 'SHA256SUMS.txt')
    Write-Host "Ready for testing: $exe"
    Write-Host "Portable archive: $archive"
} finally {
    $env:PATH = $savedPath; $env:PVS_SLIM_BUILD = $savedSlim; $env:QT_QPA_PLATFORM = $savedQt
    Pop-Location
}
