<# Rebuild the complete slim host in a separate portable directory using an installed build environment. #>
param([string]$PythonExecutable = '', [string]$OutputDirectory = 'dist\WriterPluginPreview')
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $PythonExecutable) { $PythonExecutable = Join-Path $repo '.venv-build\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $PythonExecutable)) { throw 'Install the complete host build dependencies in .venv-build first.' }
$output = [IO.Path]::GetFullPath((Join-Path $repo $OutputDirectory))
if (-not $output.StartsWith($repo + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Build output must stay inside this checkout.'
}
$work = Join-Path $repo 'build\writer-plugin-host'
$reports = Join-Path $repo 'artifacts\writer-host-build'
New-Item -ItemType Directory -Force -Path $reports | Out-Null
$savedPath = $env:PATH; $savedSlim = $env:PVS_SLIM_BUILD; $savedQt = $env:QT_QPA_PLATFORM
Push-Location $repo
try {
    # Prevent unrelated developer-tool DLLs from entering the frozen package.
    $env:PATH = (Split-Path -Parent $PythonExecutable) + ';' + (Join-Path $env:SystemRoot 'System32') + ';' + $env:SystemRoot
    $env:PVS_SLIM_BUILD = '1'; $env:QT_QPA_PLATFORM = 'offscreen'
    & $PythonExecutable -m PyInstaller --clean --noconfirm --distpath $output --workpath $work ChatterboxStudio.spec
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
    $archive = Join-Path $reports 'PlaguesVoiceStudio-WriterPlugin-Portable.zip'
    Compress-Archive -LiteralPath $folder -DestinationPath $archive -Force
    $hash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $([IO.Path]::GetFileName($archive))" | Set-Content (Join-Path $reports 'SHA256SUMS.txt')
    Write-Host "Ready for testing: $exe"
    Write-Host "Portable archive: $archive"
} finally {
    $env:PATH = $savedPath; $env:PVS_SLIM_BUILD = $savedSlim; $env:QT_QPA_PLATFORM = $savedQt
    Pop-Location
}
