param([string]$PythonExecutable = 'python', [switch]$SkipInstall,
      [string]$OutputDirectory = 'dist')
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $python = Join-Path $PSScriptRoot '.venv-build\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        & $PythonExecutable -m venv .venv-build
        if ($LASTEXITCODE -ne 0) { throw 'Could not create build environment.' }
    }
    if (-not $SkipInstall) {
        & $python -m pip install -r requirements-build.txt
        if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed.' }
    }
    & $python prepare_icon.py
    if ($LASTEXITCODE -ne 0) { throw 'Icon conversion failed.' }
    $previousQt = $env:QT_QPA_PLATFORM
    $previousHome = $env:GOODNEIGHBOR_DJ_HOME
    $previousPath = $env:PATH
    try {
        # Prevent unrelated developer-tool DLLs (Poppler/libheif, etc.) on PATH
        # from being collected instead of the Windows/Qt runtime dependencies.
        $env:PATH = @((Split-Path $python), (Join-Path $env:SystemRoot 'System32'), $env:SystemRoot) -join ';'
        $env:QT_QPA_PLATFORM = 'offscreen'
        $env:GOODNEIGHBOR_DJ_HOME = Join-Path $PSScriptRoot 'build\test-profile'
        & $python -m unittest discover -p 'tests*.py' -v
        if ($LASTEXITCODE -ne 0) { throw 'DJ Writer regression tests failed.' }
        & $python -m PyInstaller --noconfirm --clean --distpath $OutputDirectory 'Goodneighbor Plague Radio DJ Writer.spec'
        if ($LASTEXITCODE -ne 0) { throw 'Windows packaging failed.' }
        $appName = 'Goodneighbor Plague Radio DJ Writer'
        $packageFolder = Join-Path (Join-Path $PSScriptRoot $OutputDirectory) $appName
        $exe = Join-Path $packageFolder "$appName.exe"
        $report = Join-Path $PSScriptRoot ('build\smoke-' + [guid]::NewGuid().ToString('N') + '.json')
        $process = Start-Process -FilePath $exe -ArgumentList @('--smoke-test', ('"' + $report + '"')) -PassThru -WindowStyle Hidden
        if (-not $process.WaitForExit(60000)) {
            $process.Kill()
            throw 'Frozen application smoke test timed out.'
        }
        if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $report)) { throw 'Frozen application smoke test failed.' }
        $result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
        if (-not $result.ok -or -not $result.icon) { throw 'Frozen icon verification failed.' }
        New-Item -ItemType Directory -Force artifacts | Out-Null
        $zip = Join-Path $PSScriptRoot 'artifacts\DJ-Writer-Plugin-Windows.zip'
        Compress-Archive -LiteralPath $packageFolder -DestinationPath $zip -Force
        $hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash  DJ-Writer-Plugin-Windows.zip" | Set-Content artifacts\SHA256SUMS.txt
        Write-Host "Ready for testing: $exe"
        Write-Host "Portable archive: $zip"
    } finally {
        $env:QT_QPA_PLATFORM = $previousQt
        $env:GOODNEIGHBOR_DJ_HOME = $previousHome
        $env:PATH = $previousPath
    }
} finally { Pop-Location }
